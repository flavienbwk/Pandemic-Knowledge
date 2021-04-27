import csv
import os
import re
import prefect
from datetime import datetime, timedelta
from prefect import Flow, task, Client
from minio import Minio

MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT")
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY")

elastic_headers = ["date_start", "date_end", "location", "cases", "entity"]

columns_allowed = {
    "date": ["YearWeekISO", "dateRep", "date"],
    "location": ["Region", "location", "countriesAndTerritories"],
    "cases": ["NumberDosesReceived", "total_vaccinations", "cases"]
}

logger = prefect.context.get("logger")

def format_date(date):
    date = date.replace("/", "-")
    p = re.compile("(\\d{4})-W(\\d{2})")
    weekMatches = p.match(date)
    if weekMatches is not None:
        groups = weekMatches.groups()
        date_start = datetime.strptime(f'{groups[0]}-W{int(groups[1]) - 1}-1', "%Y-W%W-%w").date()
        date_end = date_start + timedelta(days=6.9)
        return date_start, date_end
    p = re.compile("(\\d{2})-(\\d{2})-(\\d{4})")
    frDateMatches = p.match(date)
    if frDateMatches is not None:
        groups = weekMatches.groups()
        date = f'{groups[2]}-{groups[1]}-{groups[0]}'
        return date, date
    p = re.compile("(\\d{4})-(\\d{2})-(\\d{2})")
    dateMatches = p.match(date)
    if dateMatches is not None:
        return date, date
    return None, None

# @task
# def insert_row(row, columns_indexes):
#     date_start, date_end = format_date(row[columns_indexes["date"]])
#     print(date_start, date_end)

@task
def parse_files(minio_client, bucket_name):
    logger.info("Parse file for bucket {}".format(bucket_name))
    if client.bucket_exists(bucket_name):
        raise("Bucket {} does not exists".format(bucket_name))
    objects = client.list_objects(bucket_name)
    for obj in objects:
        # logger.info(obj)
        pass
    # for file in files:
    #     with open("{}/{}".format(folder, file), newline='') as csvfile:
    #         spamreader = csv.reader(csvfile, quotechar=',')
    #         columns_indexes = None
    #         for row in spamreader:
    #             if columns_indexes is None:
    #                 columns_indexes = {}
    #                 columns = row
    #                 for name in columns_allowed:
    #                     for column in columns:
    #                         index = columns_allowed[name].index(column) if column in columns_allowed[name] else None
    #                         if index is None:
    #                             continue
    #                         columns_indexes[name] = index
    #                         break
    #                     if name not in columns_indexes:
    #                         raise("Header {} cannot be found in csv {}".format(name, file))
    #                 continue

def run_flow():
    with Flow("Parse and insert csv files") as flow:
        minio_client = Minio(
            MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY
        )
        files = parse_files(minio_client, "vaccination")
        files = parse_files(minio_client, "contamination")

    try:
        client = Client()
        client.create_project(project_name="pandemic-knowledge")
    except prefect.utilities.exceptions.ClientError as e:
        logger.info("Project already exists")

    flow.register(project_name="pandemic-knowledge", labels=["development"])

    # Optionally run the code now
    flow.run()

run_flow()