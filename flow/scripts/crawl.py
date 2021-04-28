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
            "title": {"type": "text"},
            "desc": {"type": "text"},
            "datetime": {"type": "text"},
            "link": {"type": "text"},
            "img": {"type": "text"},
            "media": {"type": "text"},
            "site": {"type": "text"},
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

class GetNews(Task):
    def run(self, bucket_name):
        googlenews = GoogleNews()
        googlenews.set_lang('en')
        googlenews.set_encode('utf-8')
        res = []
        lang = ["fr", "en"]
        searchtag = ["COVID", "CORONA"]
        i = 0
        for l in lang:
            res.append([])
            for i2 in searchtag:
                googlenews.get_news(i2)
                res[i].append(googlenews.results(sort=True))
                googlenews.clear()
            i += 1
        ret = {}
        i = 0
        l = 0
        while l < len(lang):
        	while i < len(res):
        		for j in res[l][i]:
        			index = str(j["title"]) + str(j["datetime"])
        			if index not in ret:
        				ret[index] = {
                            "title": str(j["title"]),
                            "desc": str(j["desc"]),
                            "img": str(j["img"]),
                            "link": str(j["link"]),
                            "link": str(j["link"]),
                            "datetime": str(j["datetime"]),
                            "TAG": []
                        }
        			ret[index]["TAG"].append([searchtag[i], lang[l]])
        		i += 1
        	l += 1
        to_inject = []
        for i in ret:
            to_inject.append(ret[i])
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

with Flow("Search news and insert") as flow:
    bucket="news"
    flow.set_dependencies(
        task=GetNews(),
        upstream_tasks=[GenerateEsMapping(bucket)],
        keyword_tasks=dict(bucket_name=bucket))

try:
    client = Client()
    client.create_project(project_name="pandemic-knowledge")
except prefect.utilities.exceptions.ClientError as e:
    logger.info("Project already exists")

flow.register(project_name="pandemic-knowledge", labels=["development"])
flow.run()
