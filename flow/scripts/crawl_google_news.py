# python3
import os
from typing import Iterable
import uuid
import prefect
from elasticsearch import Elasticsearch, helpers
from prefect import Flow, Task, Client
from datetime import timedelta, datetime
from prefect.schedules import IntervalSchedule
from GoogleNews import GoogleNews


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
            "title": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "desc": {"type": "text"},
            "date": {
                "type": "date",
                "format": "strict_date_optional_time||epoch_millis",
            },
            "link": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "img": {"type": "text"},
            "media": {"type": "text"},
            "site": {"type": "text"},
            "lang": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
        }
    }
}


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


def format_new(new: dict, lang: str) -> dict:
    """Formatting a single Google News new for elasticsearch injection"""
    if len(new):
        return {
            "title": str(new["title"]),
            "desc": str(new["desc"]),
            "img": str(new["img"]),
            "link": "https://" + str(new["link"]),
            "site": str(new["site"]),
            "date": new["datetime"],
            "lang": lang,
        }
    return None


def get_news(googlenews: GoogleNews, lang: str, search_tag: str) -> Iterable:
    googlenews.get_news(search_tag)
    news = googlenews.results(sort=True)
    if news:
        for new in news:
            fmt_new = format_new(new, lang)
            if fmt_new:
                yield fmt_new
    return []


class GetNews(Task):
    def run(self, index_name):
        googlenews = GoogleNews(
            period="24h",  # TODO(): Improve using googlenews.set_time_range('02/01/2020','02/28/2020')
            encode="utf-8",
        )
        news_to_inject = []
        langs = ["fr", "en"]
        search_tags = ["COVID", "CORONA"]
        for lang in langs:
            for search_tag in search_tags:
                logger.info(
                    f"Crawling GoogleNews for '{lang}' lang and {search_tag} search tag..."
                )
                googlenews.set_lang(lang)
                try:
                    news = list(get_news(googlenews, lang, search_tag))
                    news_to_inject += news if len(news) else []
                    logger.info(f"Found {len(news)} news.")
                except Exception as e:
                    logger.error(e)
                googlenews.clear()
                if len(news_to_inject) > 0:
                    inject_rows_to_es(news_to_inject, index_name)
                    news_to_inject = []


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


schedule = IntervalSchedule(
    start_date=datetime.utcnow() + timedelta(seconds=1), interval=timedelta(hours=24)
)
with Flow("Crawl news and insert", schedule=schedule) as flow:
    index_name = "news_googlenews"
    flow.set_dependencies(
        upstream_tasks=[GenerateEsMapping(index_name)],
        task=GetNews(),
        keyword_tasks=dict(index_name=index_name),
    )

if __name__ == "__main__":
    try:
        client = Client()
        client.create_project(project_name="pandemic-knowledge-crawl-googlenews")
    except prefect.utilities.exceptions.ClientError as e:
        logger.info("Project already exists")

    flow.register(
        project_name="pandemic-knowledge-crawl-googlenews",
        labels=["development"],
        add_default_labels=False,
    )
