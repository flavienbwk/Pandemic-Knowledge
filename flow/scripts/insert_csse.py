import os
import dateparser
import uuid
import prefect
import clevercsv
import traceback
from tqdm import tqdm
from datetime import datetime, date
from prefect import Flow, Task, Client
from minio import Minio
from elasticsearch import Elasticsearch, helpers
from geopy.geocoders import Nominatim

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

bucket_name = "contamination-csse"
project_name = f"pandemic-knowledge-{bucket_name}"

logger = prefect.context.get("logger")

columns_allowed = {
    "date": ["Last Update", "Last_Update"],
    "location": [
        "Country_Region",
        "Country/Region",
        "Province_State",
        "Province/State",
    ],
    "cases": ["Confirmed"],
    "deaths": ["Deaths"],
    "recovered": ["Recovered"],
}

extra_locations = {"EL": "GR"}

locations_cache = {}


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
    if not date:
        return None
    try:
        return dateparser.parse(date)
    except Exception as e:
        logger.error(e)
    return None


def format_location(lookup_table, location_name):
    if not location_name:
        return None
    if location_name in locations_cache:
        return locations_cache[location_name]
    if location_name in lookup_table:
        return lookup_table[location_name]

    logger.info(f"Guessing geolocation for {location_name}")
    geolocator = Nominatim(user_agent="pandemic-knowledge")
    location = geolocator.geocode(
        extra_locations[location_name]
        if location_name in extra_locations
        else location_name,
        addressdetails=True,
    )
    logger.info(f"Found {location.latitude}, {location.longitude}")

    if location and location.raw and "address" in location.raw:
        locations_cache[location_name] = (
            {"lat": location.latitude, "lon": location.longitude},
            location.raw["address"]["country_code"].upper(),
        )
        return locations_cache[location_name]
    else:
        logger.error(f"Failed to locate {location}")
        return None


def pick_one_of_elements(haystack: list, needles: list):
    for needle in needles:
        if needle in haystack:
            return needle
    return None


def pick_nonempty_cell(row, headers, potential_keys):
    for potential_key in potential_keys:
        if potential_key in headers and row[headers[potential_key]]:
            return row[headers[potential_key]]
    return None


def format_row(lookup_table, row, headers, filename):
    date_start = date_end = format_date(
        pick_nonempty_cell(row, headers, columns_allowed["date"])
    )
    location = format_location(
        lookup_table, pick_nonempty_cell(row, headers, columns_allowed["location"])
    )
    nb_cases = pick_nonempty_cell(row, headers, columns_allowed["cases"])
    nb_deaths = pick_nonempty_cell(row, headers, columns_allowed["deaths"])
    nb_recovered = pick_nonempty_cell(row, headers, columns_allowed["recovered"])
    if location and date_start and nb_cases:
        return {
            "date_start": date_start,
            "date_end": date_end,
            "location": location[0],
            "cases": int(nb_cases) if nb_cases else 0,
            "confirmed": int(nb_cases) if nb_cases else 0,
            "deaths": int(nb_deaths) if nb_deaths else 0,
            "recovered": int(nb_recovered) if nb_recovered else 0,
            "filename": filename,
            "iso_code2": location[1],
        }
    return None


def inject_rows_to_es(rows, index_name):
    es_inst = get_es_instance()

    logger.info("Injecting {} rows in Elasticsearch".format(len(rows)))

    actions = [
        {"_index": index_name, "_id": uuid.uuid4(), "_source": row} for row in rows
    ]
    helpers.bulk(es_inst, actions)


def parse_file(lookup_table, minio_client, bucket_name, object_name):
    csv_file_path = "/tmp/" + str(uuid.uuid4())
    minio_client.fget_object(bucket_name, object_name, csv_file_path)
    with open(csv_file_path, "r", newline="") as fp:
        char_read = 10000 if os.path.getsize(csv_file_path) > 10000 else None

        try:
            dialect = clevercsv.Sniffer().sniff(fp.read(char_read), verbose=True)
        except Exception as e:
            logger.error(e)
            return []

        fp.seek(0)
        reader = clevercsv.reader(fp, dialect)
        headers_list = next(reader)
        headers = {}
        for i, header in enumerate(headers_list):
            headers[header] = i
        for row in tqdm(reader, unit="entry"):
            yield format_row(lookup_table, row, headers, object_name)
    return []


class ParseFile(Task):
    def run(self, lookup_table, index_name, bucket_name, object_name):
        minio_client = Minio(
            MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=MINIO_SCHEME == "https",
        )
        to_inject = []
        logger.info(f"Processing {object_name}...")
        for row in parse_file(lookup_table, minio_client, bucket_name, object_name):
            if row is not None:
                to_inject.append(row)
                if len(to_inject) >= MAX_ES_ROW_INJECT:
                    inject_rows_to_es(to_inject, index_name)
                    to_inject = []
            else:
                logger.info("Invalid row : ", row)
        if len(to_inject) > 0:
            inject_rows_to_es(to_inject, index_name)


def get_files(bucket_name):
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
    return list(minio_client.list_objects(bucket_name))


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


def read_lookup_table(lookup_file_path: str):
    lookup = {}
    with open(lookup_file_path, "r", newline="") as fp:
        char_read = 10000 if os.path.getsize(lookup_file_path) > 10000 else None

        try:
            dialect = clevercsv.Sniffer().sniff(fp.read(char_read), verbose=True)
        except Exception as e:
            logger.error(e)
            return {}

        fp.seek(0)
        reader = clevercsv.reader(fp, dialect)
        next(reader)
        for row in tqdm(reader, unit="entry"):
            for location in [
                row[6],  # Province_State
                row[7],  # Country_Region
                row[10],  # Combined_Key
            ]:
                if location and location not in lookup:
                    if row[8] and row[9]:  # Lat, Long
                        lookup[location] = (
                            {"lat": float(row[8]), "lon": float(row[9])},
                            row[1],
                        )
    return lookup


if __name__ == "__main__":
    with Flow("Parse and insert CSV files") as flow:
        logger.info("Loading lookup table...")
        lookup_table = read_lookup_table("/usr/app/UID_ISO_FIPS_LookUp_Table.csv")
        logger.info(f"Found {len(lookup_table)} locations.")
        for file in tqdm(get_files(bucket_name=bucket_name)):
            object_name = file.object_name
            try:
                file_date = format_date(object_name[:-4])
                if not file_date:
                    raise ValueError(f"main: No date found for file {object_name}")
                index_name = f"{bucket_name.replace('-', '_')}_{date.strftime(file_date, '%Y')}_{date.strftime(file_date, '%m')}_{date.strftime(file_date, '%d')}"
                logger.info(f"Process for index {index_name}...")
                flow.set_dependencies(
                    upstream_tasks=[GenerateEsMapping(index_name)],
                    task=ParseFile(),
                    keyword_tasks=dict(
                        lookup_table=lookup_table,
                        index_name=index_name,
                        bucket_name=bucket_name,
                        object_name=object_name,
                    ),
                )
            except Exception as e:
                logger.error(traceback.format_exc())
                logger.error(e)
                logger.error(f"Can't process object {object_name}")

    try:
        client = Client()
        client.create_project(project_name=project_name)
    except prefect.utilities.exceptions.ClientError as e:
        logger.info("Project already exists")

    flow.register(
        project_name=project_name, labels=["development"]
    )
