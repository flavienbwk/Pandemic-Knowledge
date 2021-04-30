#python3
import os
import json
import uuid
import prefect
from elasticsearch import Elasticsearch, helpers
from ssl import create_default_context
from geopy.geocoders import Nominatim
from iso3166 import countries
from prefect import Flow, Task, Client
from datetime import datetime
from datetime import date, timedelta

import snscrape.modules.twitter as sntwitter
import pandas

# Creating list to append tweet data to
tweets_list1 = []

# Using TwitterSearchScraper to scrape data and append tweets to list

MAX_ES_ROW_INJECT = int(os.environ.get("MAX_ES_ROW_INJECT", 1000))
ELASTIC_SCHEME = os.environ.get("ELASTIC_SCHEME")
ELASTIC_PORT = os.environ.get("ELASTIC_PORT")
ELASTIC_USER = os.environ.get("ELASTIC_USER")
ELASTIC_PWD = os.environ.get("ELASTIC_PWD")
ELASTIC_ENDPOINT = os.environ.get("ELASTIC_ENDPOINT")

logger = prefect.context.get("logger")

mapping = {
    "mappings": {
        "properties": {
            "date": {"type": "text"},
            "tweet_id": {"type": "text"},
            "content": {"type": "text"},
            "username": {"type": "text"},
        }
    }
}

def get_es_instance():
    es_inst = Elasticsearch(
        [ELASTIC_ENDPOINT],
        http_auth=(ELASTIC_USER, ELASTIC_PWD),
        scheme=ELASTIC_SCHEME,
        port=ELASTIC_PORT,
        verify_certs=False
    )
    return es_inst

def inject_rows_to_es(rows, bucket_name):
    es_inst = get_es_instance()

    logger.info("Injecting {} rows in Elasticsearch".format(len(rows)))

    actions = [
        {
            "_index": bucket_name,
            "_id": uuid.uuid4(),
            "_source": row
        }
        for row in rows
    ]

    helpers.bulk(es_inst, actions)

class GetTweets(Task):
    def run(self, bucket_name):
        d = datetime.now() - timedelta(days=1)
        limit = d.strftime("%y-%m-%d")
        to_inject = []
        for i,tweet in enumerate(sntwitter.TwitterSearchScraper("covid since:" + limit).get_items()):
            if i>300:
                break
            to_inject.append({
                "date": tweet.date,
                "tweet_id": tweet.id,
                "content": tweet.content,
                "username": tweet.username
                })
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
            index=index_name,
            body=mapping,
            ignore=400
        )

        if 'acknowledged' in response:
            if response['acknowledged'] == True:
                logger.info("INDEX MAPPING SUCCESS FOR INDEX: {}".format(response['index']))
            elif 'error' in response:
                logger.error(response['error']['root_cause'])
                logger.error("Error type: {}".format(response['error']['type']))
                raise Exception("Unable to create index mapping")

with Flow("Search tweets and insert") as flow:
    bucket="tweets"
    flow.set_dependencies(
        task=GetTweets(),
        upstream_tasks=[GenerateEsMapping(bucket)],
        keyword_tasks=dict(bucket_name=bucket))

try:
    client = Client()
    client.create_project(project_name="pandemic-knowledge")
except prefect.utilities.exceptions.ClientError as e:
    logger.info("Project already exists")

flow.register(project_name="pandemic-knowledge", labels=["development"])
flow.run()
