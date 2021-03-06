import os
import re
import uuid
import prefect
import clevercsv
from tqdm import tqdm
from datetime import datetime, timedelta
from prefect import Flow, Task, Client
from minio import Minio
from elasticsearch import Elasticsearch, helpers
from ssl import create_default_context
from geopy.geocoders import Nominatim
from iso3166 import countries
from prefect.schedules import IntervalSchedule

from mapping import mapping

MINIO_SCHEME = os.environ.get("MINIO_SCHEME")
MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT")
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY")
MAX_ES_ROW_INJECT = int(os.environ.get("MAX_ES_ROW_INJECT", 1000))
ELASTIC_SCHEME = os.environ.get("ELASTIC_SCHEME")
ELASTIC_PORT = os.environ.get("ELASTIC_PORT")
ELASTIC_USER = os.environ.get("ELASTIC_USER")
ELASTIC_PWD = os.environ.get("ELASTIC_PWD")
ELASTIC_ENDPOINT = os.environ.get("ELASTIC_ENDPOINT")

columns_allowed = {
    "date": ["YearWeekISO", "dateRep", "date"],
    "location": ["ReportingCountry", "location", "countriesAndTerritories"],
    "cases": ["NumberDosesReceived", "new_vaccinations", "cases", "new_cases"],
    "population": ["population"],
}

logger = prefect.context.get("logger")

extra_locations = {"EL": "GR"}

locations_cache = {"World": None}


def get_es_instance():
    es_inst = Elasticsearch(
        [ELASTIC_ENDPOINT],
        http_auth=(ELASTIC_USER, ELASTIC_PWD),
        scheme=ELASTIC_SCHEME,
        port=ELASTIC_PORT,
        verify_certs=False,
    )
    return es_inst


def format_date(date):
    date = date.replace("/", "-")
    p = re.compile("(\\d{4})-W(\\d{2})")
    weekMatches = p.match(date)
    if weekMatches is not None:
        groups = weekMatches.groups()
        date_start = datetime.strptime(
            f"{groups[0]}-W{int(groups[1]) - 1}-1", "%Y-W%W-%w"
        ).date()
        date_end = date_start + timedelta(days=6.9)
        return date_start.strftime("%Y-%m-%d"), date_end.strftime("%Y-%m-%d")
    p = re.compile("(\\d{2})-(\\d{2})-(\\d{4})")
    frDateMatches = p.match(date)
    if frDateMatches is not None:
        groups = frDateMatches.groups()
        date = f"{groups[2]}-{groups[1]}-{groups[0]}"
        return date, date
    p = re.compile("(\\d{4})-(\\d{2})-(\\d{2})")
    dateMatches = p.match(date)
    if dateMatches is not None:
        return date, date
    return None, None


def format_location(location_name):
    if location_name in locations_cache:
        return locations_cache[location_name]
    geolocator = Nominatim(user_agent="pandemic-knowledge")
    location = geolocator.geocode(
        extra_locations[location_name]
        if location_name in extra_locations
        else location_name,
        addressdetails=True,
    )

    if location is None or "country_code" not in location.raw["address"]:
        logger.info(location_name)
        locations_cache[location_name] = None
        return None

    iso2 = location.raw["address"]["country_code"].upper()

    iso3 = countries.get(iso2).alpha3

    locations_cache[location_name] = (
        {"lat": location.latitude, "lon": location.longitude},
        iso2,
    )

    return locations_cache[location_name]


def format_row(row, columns_indexes, filename, bucket_name):
    date_start, date_end = format_date(row[columns_indexes["date"]])
    location = format_location(row[columns_indexes["location"]])
    if location is None:
        return None
    max_population = (
        int(float(row[columns_indexes["population"]]))
        if row[columns_indexes["population"]] != ""
        else 0
    )
    cases = (
        int(float(row[columns_indexes["cases"]]))
        if row[columns_indexes["cases"]] != ""
        else 0
    )
    percentage = (
        float(cases) / float(max_population) * 100 if max_population != 0 else None
    )

    formatted = {
        "date_start": date_start,
        "date_end": date_end,
        "location": location[0],
        "filename": filename,
        "iso_code2": location[1],
        "max_population": max_population,
        "percentage": percentage,
    }

    formatted["vaccinated" if bucket_name == "vaccination" else "confirmed"] = cases

    return formatted


def inject_rows_to_es(rows, bucket_name):
    es_inst = get_es_instance()

    logger.info("Injecting {} rows in Elasticsearch".format(len(rows)))

    actions = [
        {"_index": bucket_name, "_id": uuid.uuid4(), "_source": row} for row in rows
    ]

    helpers.bulk(es_inst, actions)


def parse_file(minio_client, obj):
    csv_file_path = "/tmp/" + str(uuid.uuid4())
    minio_client.fget_object(obj.bucket_name, obj.object_name, csv_file_path)
    with open(csv_file_path, "r", newline="") as fp:
        char_read = 100000 if os.path.getsize(csv_file_path) > 100000 else None

        try:
            dialect = clevercsv.Sniffer().sniff(fp.read(char_read), verbose=True)
        except Exception as e:
            logger.error(e)
            return []

        fp.seek(0)
        reader = clevercsv.reader(fp, dialect)
        headers = next(reader)
        columns_indexes = {}
        malformed_csv = False
        for name in columns_allowed:
            for header in headers:
                index = (
                    headers.index(header) if header in columns_allowed[name] else None
                )
                if index is None:
                    continue
                columns_indexes[name] = index
                break
            if name not in columns_indexes:
                logger.error(
                    "Header {} cannot be found in csv {}".format(name, obj.object_name)
                )
                malformed_csv = True
                continue
        if malformed_csv is True:
            return []
        for row in tqdm(reader, unit="entry"):
            row = format_row(row, columns_indexes, obj.object_name, obj.bucket_name)
            if row is not None:
                yield row
    return []


class ParseFiles(Task):
    def run(self, bucket_name):
        minio_client = Minio(
            MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=MINIO_SCHEME == "https",
        )
        logger.info("Parse file for bucket {}".format(bucket_name))
        if not minio_client.bucket_exists(bucket_name):
            logger.error("Bucket {} does not exists".format(bucket_name))
            return
        objects = minio_client.list_objects(bucket_name)
        for obj in objects:
            to_inject = []
            for row in parse_file(minio_client, obj):
                to_inject.append(row)
                if len(to_inject) >= MAX_ES_ROW_INJECT:
                    inject_rows_to_es(to_inject, bucket_name)
                    to_inject = []
            if len(to_inject) > 0:
                inject_rows_to_es(to_inject, bucket_name)


class GenerateEsMapping(Task):
    def __init__(self, index_name, **kwargs):
        self.index_name = index_name
        super().__init__(**kwargs)

    def run(self):
        index_name = self.index_name
        es_inst = get_es_instance()

        logger.info("Generating mapping for index {}".format(index_name))

        es_inst.indices.delete(index=index_name, ignore=[400, 404])

        response = es_inst.indices.create(
            index=index_name, body=mapping, ignore=400  # ignore 400 already exists code
        )

        if "acknowledged" in response:
            if response["acknowledged"] == True:
                logger.info(
                    "INDEX MAPPING SUCCESS FOR INDEX: {}".format(response["index"])
                )
            elif "error" in response:
                logger.error(response["error"]["root_cause"])
                logger.error("Error type: {}".format(response["error"]["type"]))
                raise Exception("Unable to create index mapping")


schedule = IntervalSchedule(
    interval=timedelta(hours=24), start_date=datetime.utcnow() + timedelta(seconds=1)
)

with Flow("Parse and insert csv files", schedule) as flow:
    for bucket in ["vaccination", "contamination"]:
        flow.set_dependencies(
            task=ParseFiles(),
            upstream_tasks=[GenerateEsMapping(bucket)],
            keyword_tasks=dict(bucket_name=bucket),
        )

try:
    client = Client()
    client.create_project(project_name="pandemic-knowledge")
except prefect.utilities.exceptions.ClientError as e:
    logger.info("Project already exists")

flow.register(project_name="pandemic-knowledge", labels=["development"])