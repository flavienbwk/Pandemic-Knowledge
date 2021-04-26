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

We need to create a _tenant_. Execute on your host :

```bash
pip3 install prefect
prefect backend server
prefect server create-tenant --name default --slug default
```
