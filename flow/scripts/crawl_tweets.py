# python3
import os
import uuid
import prefect
from elasticsearch import Elasticsearch, helpers
from prefect import Flow, Task, Client
from datetime import datetime
from datetime import timedelta

from prefect.schedules import IntervalSchedule
import snscrape.modules.twitter as sntwitter

from crawl_mapping import mapping

project_name = "pandemic-knowledge-crawl-tweets"
index_name = "news_tweets"

lang = "en"
tweet_limit = 1000

MAX_ES_ROW_INJECT = int(os.environ.get("MAX_ES_ROW_INJECT", 1000))
ELASTIC_SCHEME = os.environ.get("ELASTIC_SCHEME")
ELASTIC_PORT = os.environ.get("ELASTIC_PORT")
ELASTIC_USER = os.environ.get("ELASTIC_USER")
ELASTIC_PWD = os.environ.get("ELASTIC_PWD")
ELASTIC_ENDPOINT = os.environ.get("ELASTIC_ENDPOINT")

logger = prefect.context.get("logger")

schedule = IntervalSchedule(
    start_date=datetime.utcnow() + timedelta(seconds=1), interval=timedelta(hours=24)
)


def get_es_instance():
    es_inst = Elasticsearch(
        [ELASTIC_ENDPOINT],
        http_auth=(ELASTIC_USER, ELASTIC_PWD),
        scheme=ELASTIC_SCHEME,
        port=ELASTIC_PORT,
        verify_certs=False,
    )
    return es_inst


def inject_rows_to_es(rows, index_name):
    es_inst = get_es_instance()

    logger.info("Injecting {} rows in Elasticsearch".format(len(rows)))

    actions = [
        {"_index": index_name, "_id": uuid.uuid4(), "_source": row} for row in rows
    ]

    helpers.bulk(es_inst, actions)


class GetTweets(Task):
    def run(self, index_name):
        tweets_from = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        to_inject = []
        tweets = sntwitter.TwitterSearchScraper(
            f"covid since:{tweets_from} lang:{lang}"
        ).get_items()
        for i, tweet in enumerate(tweets):
            if i > tweet_limit:
                break
            to_inject.append(
                {
                    "title": f"Tweet from {tweet.username} the {tweet.date}",
                    "desc": tweet.content,
                    "date": tweet.date,
                    "link": tweet.url,
                    "source.crawler": "twitter",
                    "source.website": "https://twitter.com",
                    "source.author": tweet.username,
                    "source.url": tweet.url,
                    "source.tweet.id": tweet.id,
                    "lang": lang
                }
            )
        if len(to_inject) > 0:
            inject_rows_to_es(to_inject, index_name)


class GenerateEsMapping(Task):
    def __init__(self, index_name, **kwargs):
        self.index_name = index_name
        super().__init__(**kwargs)

    def run(self):
        index_name = self.index_name
        es_inst = get_es_instance()

        logger.info("Generating mapping for index {}".format(index_name))

        es_inst.indices.delete(index=index_name, ignore=[400, 404])

        response = es_inst.indices.create(index=index_name, body=mapping, ignore=400)

        if "acknowledged" in response:
            if response["acknowledged"] == True:
                logger.info(
                    "INDEX MAPPING SUCCESS FOR INDEX: {}".format(response["index"])
                )
            elif "error" in response:
                logger.error(response["error"]["root_cause"])
                logger.error("Error type: {}".format(response["error"]["type"]))
                raise Exception("Unable to create index mapping")


with Flow("Crawl tweets and insert", schedule=schedule) as flow:
    flow.set_dependencies(
        upstream_tasks=[GenerateEsMapping(index_name)],
        task=GetTweets(),
        keyword_tasks=dict(index_name=index_name),
    )

if __name__ == "__main__":
    try:
        client = Client()
        client.create_project(project_name=project_name)
    except prefect.utilities.exceptions.ClientError as e:
        logger.info("Project already exists")

    flow.register(
        project_name=project_name,
        labels=["development"],
        add_default_labels=False,
    )
