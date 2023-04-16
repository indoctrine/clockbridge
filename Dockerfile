FROM python:3.8-slim-buster
MAINTAINER Meta <meta@meta.id.au>

WORKDIR /clockbridge
VOLUME /opt/clockbridge:/clockbridge

COPY requirements.txt requirements.txt
RUN pip3 install --upgrade pip
RUN pip3 install -r requirements.txt

COPY . .

CMD ["python3", "-m", "flask", "run", "--host=0.0.0.0"]
