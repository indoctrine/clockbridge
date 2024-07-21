FROM nginx:stable

LABEL author="Meta <meta@meta.id.au>"

WORKDIR /clockbridge
VOLUME /config
ENV PIP_ROOT_USER_ACTION=ignore
ENV CLOCKBRIDGE_CONFIG_PATH=/config/config.yaml

COPY nginx/nginx.conf /etc/nginx/conf.d/default.conf
RUN apt-get update && apt-get install python3 python3-pip -y

COPY . . 
RUN --mount=type=cache,target=/root/.cache/pip pip3 install -r /clockbridge/requirements.txt --break-system-packages

EXPOSE 5000
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
