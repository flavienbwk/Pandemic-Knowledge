FROM python:3.8

RUN apt-get install gcc

RUN python3 -m pip install prefect
COPY prefect.config /root/.prefect/config.toml

ENTRYPOINT \
    prefect backend server && \
    prefect server create-tenant --name default --slug default
