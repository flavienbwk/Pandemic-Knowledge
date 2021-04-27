FROM python:3.7

RUN apt update && apt install uuid -y

COPY ./requirements.txt /requirements.txt

RUN pip install -r /requirements.txt