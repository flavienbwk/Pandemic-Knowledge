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

### Run Prefect workers

Agents are services that run your scheduled flows.

Open and edit the [`agent/config.toml`](./agent/config.toml) file.

> :information_source: In each `config.toml`, you will find the `172.17.0.1` IP address. This is the IP of the Docker daemon on which are exposed all exposed ports of your containers. This allows   containers on launched from different docker-compose networks to communicate. Change it if yours is different (check your daemon IP by typing `ip a | grep docker0`).
> 
> ![Docker interface IP](./docker_interface.png)
> 
> Here, mine is `192.168.254.1` but the default is generally to `172.17.0.1`.

Then you can run :

```bash
docker-compose -f agent/docker-compose.yml up -d
```

> :information_source: You can run the agent on another machine than the one with the Prefect server. Edit the [`agent/config.toml`](./agent/config.toml) file for that.

Maybe you want to instanciate multiple agents automatically ?

```bash
docker-compose -f agent/docker-compose.yml up -d --build --scale agent=3 agent
```

### Inject COVID-19 data

There are several data source supported by Pandemic Knowledge

- CSSE at Johns Hopkins University [daily reports](https://github.com/CSSEGISandData/COVID-19/tree/master/csse_covid_19_data/csse_covid_19_daily_reports) (from 02/01/2020)
  - docker-compose slug : `insert_csse_contamination`
  - MinIO bucket : `contamination-csse`
  - Format : CSV

Start MinIO and import your files according to the buckets evoked upper :

```bash
docker-compose up -d minio
```

> MinIO is available at `localhost:9000`

Download dependencies and start the injection service of your choice. For instance :

```bash
pip3 install -r ./flow/requirements.txt
docker-compose -f insert.docker-compose.yml up --build insert_csse_contamination
```
