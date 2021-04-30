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
            "source": {
                "properties": {
                    "crawler": {"type": "string"},
                    "website": {"type": "string"},
                    "author": {"type": "string"},
                    "url": {"type": "string"},
                    "tweet": {"id": {"type": "string"}},
                }
            },
            "lang": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
        }
    }
}