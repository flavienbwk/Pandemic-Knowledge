mapping = {
    "mappings": {
        "properties": {
            "date_start": {
                "type": "date",
                "format": "strict_date_optional_time||epoch_millis",
            },
            "date_end": {
                "type": "date",
                "format": "strict_date_optional_time||epoch_millis",
            },
            "location": {"type": "geo_point"},
            "location_name": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword"}},
            },
            "confirmed": {"type": "long"},
            "deaths": {"type": "long"},
            "vaccinated": {"type": "long"},
            "tested": {"type": "long"},
            "recovered": {"type": "long"},
            "filename": {"type": "text"},
            "iso_code2": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "iso_region2": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "max_population": {"type": "long"},
            "percentage": {"type": "float"},
        }
    }
}