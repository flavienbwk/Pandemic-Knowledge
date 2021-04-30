FROM python:3.7 as python37

RUN apt update
RUN pip install --upgrade pip

COPY ./requirements.txt /requirements.txt

RUN pip install -r /requirements.txt




FROM python:3.8 as python38

RUN apt update
RUN pip install --upgrade pip

COPY ./requirements.txt /requirements.txt

RUN pip install -r /requirements.txt
