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
                    "crawler": {"type": "text"},
                    "website": {"type": "text"},
                    "author": {"type": "text"},
                    "url": {"type": "text"},
                    "tweet": {"properties": {"id": {"type": "text"}}},
                }
            },
            "lang": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
        }
    }
}