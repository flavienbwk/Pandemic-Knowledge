# Pandemic-Knowledge

A fully-featured dashboard for extracting knowledge from Covid data.

## Install

### Initialize elasticsearch

```bash
docker-compose -f create-certs.yml run --rm create_certs
```

```bash
docker-compose up -d
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

We need to create a _tenant_. Execute on your host :

```bash
pip3 install prefect
prefect backend server
prefect server create-tenant --name default --slug default
```

Accédez à l'interface via [localhost:8081](http://localhost:8081)
