import os
import dateparser
import uuid
import requests
import prefect
import clevercsv
from tqdm import tqdm
from prefect import Flow, Task, Client, task
from datetime import timedelta, datetime
from prefect.schedules import IntervalSchedule
from elasticsearch import Elasticsearch, helpers
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

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

csv_endpoint = "https://static.data.gouv.fr/resources/donnees-relatives-aux-resultats-des-tests-virologiques-covid-19/20210428-190945/sp-pos-quot-dep-2021-04-28-19h09.csv"
project_name = f"pandemic-knowledge-santepublic-tests"
index_name = "contamination_santepublique_vir_tests_fr"
flow_name = project_name

logger = prefect.context.get("logger")

columns_allowed = {
    "date": ["jour"],
    "location": ["dep"],
    "location_name": ["dep"],
    "cases": [],
    "confirmed": ["P"],
    "deaths": [],
    "recovered": [],
    "vaccinated": [],
    "tested": ["T"],
}

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
    location_name = pick_nonempty_cell(row, headers, columns_allowed["location_name"])
    nb_cases = pick_nonempty_cell(row, headers, columns_allowed["cases"])
    nb_deaths = pick_nonempty_cell(row, headers, columns_allowed["deaths"])
    nb_recovered = pick_nonempty_cell(row, headers, columns_allowed["recovered"])
    nb_vaccinated = pick_nonempty_cell(row, headers, columns_allowed["vaccinated"])
    nb_tested = pick_nonempty_cell(row, headers, columns_allowed["tested"])
    if date_start != None:
        return {
            "date_start": date_start,
            "date_end": date_end,
            "location": location[0] if location else None,
            "location_name": location_name,
            "cases": int(float(nb_cases)) if nb_cases else 0,
            "confirmed": int(float(nb_cases)) if nb_cases else 0,
            "deaths": int(float(nb_deaths)) if nb_deaths else 0,
            "recovered": int(float(nb_recovered)) if nb_recovered else 0,
            "vaccinated": int(float(nb_vaccinated)) if nb_vaccinated else 0,
            "tested": int(float(nb_tested)) if nb_tested else 0,
            "filename": filename,
            "iso_code2": location[1] if location else None,
            "iso_region2": f"FR-{row[2]}",
        }
    logger.warning(f"format_row(): Invalid row : {row}")
    return None


def inject_rows_to_es(rows, index_name):
    es_inst = get_es_instance()

    logger.info("Injecting {} rows in Elasticsearch".format(len(rows)))

    actions = [
        {"_index": index_name, "_id": uuid.uuid4(), "_source": row} for row in rows
    ]
    helpers.bulk(es_inst, actions)


def parse_file(lookup_table, file_path):
    with open(file_path, "r", newline="") as fp:
        char_read = 10000 if os.path.getsize(file_path) > 10000 else None

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
            yield format_row(lookup_table, row, headers, file_path)
    return []


def process_file(lookup_table, index_name, file_path):
    to_inject = []
    logger.info(f"process_file(): Processing {file_path}...")
    for row in parse_file(lookup_table, file_path):
        if row is not None:
            to_inject.append(row)
            if len(to_inject) >= MAX_ES_ROW_INJECT:
                inject_rows_to_es(to_inject, index_name)
                to_inject = []
        else:
            logger.warning("process_file(): Invalid row")
    if len(to_inject) > 0:
        inject_rows_to_es(to_inject, index_name)


class ParseFiles(Task):
    def run(self, lookup_table, index_name, http_csv_uris: list):
        for file_uri in tqdm(http_csv_uris):
            logger.info(f"Processing file {file_uri}...")
            file_path = f"/tmp/{uuid.uuid4()}"
            session = requests.Session()
            retry = Retry(connect=3, backoff_factor=0.5)
            adapter = HTTPAdapter(max_retries=retry)
            session.mount("http://", adapter)
            session.mount("https://", adapter)
            r = session.get(file_uri, allow_redirects=True)
            with open(file_path, "wb") as f:
                f.write(r.content)
            process_file(lookup_table, index_name, file_path)


class GenerateEsMapping(Task):
    def run(self, index_name) -> str:
        """
        Returns:
            str: index_name
        """
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
        return index_name


def read_lookup_table(lookup_file_path: str):
    logger.info("Loading lookup table...")
    lookup = {}
    with open(lookup_file_path, "r", newline="") as fp:
        char_read = 10000 if os.path.getsize(lookup_file_path) > 10000 else None
        dialect = clevercsv.Sniffer().sniff(fp.read(char_read), verbose=True)
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
    logger.info(f"Found {len(lookup)} locations.")
    return lookup


lookup_table = read_lookup_table("/usr/app/UID_ISO_FIPS_LookUp_Table.csv")

schedule = IntervalSchedule(
    start_date=datetime.utcnow() + timedelta(seconds=1), interval=timedelta(hours=24)
)
with Flow(flow_name, schedule=schedule) as flow:
    es_mapping_task = GenerateEsMapping()
    index_name = es_mapping_task(index_name)

    parse_files_task = ParseFiles()
    parse_files_task(
        lookup_table=lookup_table,
        index_name=index_name,
        http_csv_uris=[csv_endpoint],
    )

if __name__ == "__main__":

    try:
        client = Client()
        client.create_project(project_name=project_name)
    except prefect.utilities.exceptions.ClientError as e:
        logger.info("Project already exists")

    flow.register(
        project_name=project_name, labels=["development"], add_default_labels=False
    )
