FROM python:3.12.13-slim-bookworm
LABEL author="Meta <meta@meta.id.au>"
LABEL app="Clockbridge"

WORKDIR /clockbridge
VOLUME /config
ENV CLOCKBRIDGE_CONFIG_PATH=/config/config.yaml

COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel \
 && pip install -r requirements.txt

COPY . .

RUN useradd -m -s /bin/bash clockbridge
RUN chown -R clockbridge:clockbridge $(pwd)
USER clockbridge

EXPOSE 5000
ENTRYPOINT ["gunicorn", "-b", "0.0.0.0:5000", "-w", "4", "app:app"]