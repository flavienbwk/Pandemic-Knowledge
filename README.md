# Pandemic-Knowledge

A fully-featured dashboard for extracting knowledge from Covid data.

## Install

### Initialize elasticsearch

First, you will need to raise your host's ulimits for ElasticSearch to handle high I/O :

```bash
sudo sysctl -w vm.max_map_count=500000
```

Then :

```bash
docker-compose -f create-certs.yml run --rm create_certs
```

```bash
docker-compose up -d es01 es02 es03 kibana
```

### Initialize Prefect

Create a `~/.prefect/config.toml` file with the following content :

```bash
# debug mode
debug = true

# base configuration directory (typically you won't change this!)
home_dir = "~/.prefect"

backend = "server"

[server]
host = "http://172.17.0.1"
port = "4200"
host_port = "4200"
endpoint = "${server.host}:${server.port}"
```

Run Prefect :

```bash
docker-compose up -d prefect_postgres prefect_hasura prefect_graphql prefect_towel prefect_apollo prefect_ui
```

We need to create a _tenant_. Execute on your host :

```bash
pip3 install prefect
prefect backend server
prefect server create-tenant --name default --slug default
```

Access the web UI at [localhost:8081](http://localhost:8081)
