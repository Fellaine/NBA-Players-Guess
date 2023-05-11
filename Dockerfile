FROM python:3.11-alpine

ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1

RUN mkdir /NBAGuess
WORKDIR /NBAGuess

COPY ./requirements.txt /requirements.txt

RUN pip install -r /requirements.txt

COPY . .