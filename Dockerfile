ARG CODE_VERSION=3.8-slim-buster

FROM python:${CODE_VERSION}
LABEL author="Meta <meta@meta.id.au>"

VOLUME /opt/clockbridge:/clockbridge
WORKDIR /clockbridge
ENV PIP_ROOT_USER_ACTION=ignore
ENV CLOCKBRIDGE_CONFIG_PATH=/clockbridge/config.yaml

COPY requirements.txt requirements.txt
RUN pip3 install --upgrade pip
RUN pip3 install -r requirements.txt

COPY . .

CMD ["gunicorn", "-b", "0.0.0.0:8080", "-w 4", "app:app"]
