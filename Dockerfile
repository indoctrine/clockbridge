FROM python:3.12

LABEL author="Meta <meta@meta.id.au>"
LABEL app="Clockbridge"

WORKDIR /clockbridge
VOLUME /config
ENV PIP_ROOT_USER_ACTION=ignore
ENV CLOCKBRIDGE_CONFIG_PATH=/config/config.yaml

RUN apt-get update && apt-get install python3 python3-pip -y

COPY . . 
RUN --mount=type=cache,target=/root/.cache/pip pip3 install -r /clockbridge/requirements.txt --break-system-packages

EXPOSE 5000
ENTRYPOINT ["gunicorn", "-b", "0.0.0.0:5000", "app:app"]
