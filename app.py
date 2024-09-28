import os
import sys
import logging
from clockbridgeconfig import Config
import webhook
from flask import Flask, Response, request

# Kludge libraries
import requests
import urllib3
from datetime import datetime, timezone
import json

file_path = os.environ.get('CLOCKBRIDGE_CONFIG_PATH')
if not file_path:
    file_path = os.path.join(os.getcwd(), 'config.yaml')

app = Flask(__name__)
config = Config(file_path)
logging.info("Configuration loaded from %s, logging at %s level", file_path, config.log_level)

logger = logging.getLogger(__name__)
logging.basicConfig(format='%(asctime)s [%(levelname)s] %(message)s',
                    stream=sys.stderr)
logger.setLevel(config.log_level)

@app.route("/ping", methods = ['GET'])
def ping():
    return "Pong\n"

@app.route("/webhook/clockify", methods = ['POST'])
def clockbridge():
    try:
        logger.info("Incoming payload")
        hook = webhook.Webhook(config)
        logger.debug("Payload received with headers:\n %s", dict(request.headers))
        logger.debug("Payload contents:\n %s", json.dumps(request.json, indent=4))
        payload = hook.verify_incoming_webhook(request.headers, request.data)
        if not payload:
            return Response("Unauthorized", 403)
    except ValueError:
        return Response("Malformed request body", 400)

    try:
        # From here on out is just kludge code to make this work because I'm bored of manually entering data
        urllib3.disable_warnings(category=urllib3.exceptions.InsecureRequestWarning)
        now = datetime.now().astimezone()
        index_name = f"{config.elastic_creds['index_prefix']}-{now.strftime('%Y-%m')}"
        payload['@timestamp'] = now.strftime('%Y-%m-%dT%H:%M:%S%z')
        pwd = config.elastic_creds['password'].decode().strip()

        health = requests.get(
                    f"{config.elastic_creds['url']}_cluster/health?wait_for_status=yellow&timeout=50s",
                    auth=(config.elastic_creds['username'], pwd),
                    verify=not config.elastic_creds['insecure'],
                    headers={"Content-Type": "application/json"},
                    timeout=50
                    )
        logger.info("Elasticsearch health check returned %s", health.json()['status'])

        if health.ok:
            logger.info("Elasticsearch endpoint up, pushing data...")
            if hook.action == "TIME_ENTRY_DELETED":
                r = delete_doc(url=config.elastic_creds['url'],
                               index=index_name,
                               doc_id=payload['id'],
                               user=config.elastic_creds['username'],
                               pwd=pwd
                               )

            elif hook.action == "TIME_ENTRY_UPDATED":
                r = delete_doc(url=config.elastic_creds['url'],
                               index=index_name,
                               doc_id=payload['id'],
                               user=config.elastic_creds['username'],
                               pwd=pwd
                               )
                r = create_doc(url=config.elastic_creds['url'],
                               index=index_name,
                               doc_id=payload['id'],
                               user=config.elastic_creds['username'],
                               pwd=pwd,
                               data=payload
                               )
            else:
                r = create_doc(url=config.elastic_creds['url'],
                               index=index_name,
                               doc_id=payload['id'],
                               user=config.elastic_creds['username'],
                               pwd=pwd,
                               data=payload
                               )
            return r

        raise requests.exceptions.HTTPError(health.content)

    except Exception:
        return Response(503)

def delete_doc(url, index, doc_id, user, pwd, verify_ssl=False):
    try:
        r = requests.delete(f"{url}{index}/_doc/{doc_id}",
                        auth=(user, pwd),
                        verify=verify_ssl,
                        headers={"Content-Type": "application/json"},
                        timeout=10
                    )
        if r.ok:
            logger.info("Deleted existing document from Elasticsearch:\n %s", r.content)
            return r.content
        else:
            raise requests.exceptions.HTTPError(r.content)
    except Exception as e:
        logger.exception("Unable to delete document from Elasticsearch\n %s", e)

def create_doc(url, index, doc_id, user, pwd, data, verify_ssl=False):
    try:
        r = requests.post(f"{url}{index}/_create/{doc_id}",
                        data=json.dumps(data),
                        auth=(user, pwd),
                        verify=verify_ssl,
                        headers={"Content-Type": "application/json"},
                        timeout=10
                    )
        if r.ok:
            logger.info("Created new document in Elasticsearch:\n %s", r.content)
            return r.content
        else:
            raise requests.exceptions.HTTPError(r.content)
    except Exception as e:
        logger.exception("Unable to create document in Elasticsearch\n %s", e)

if __name__ == "__main__":
    app.run(debug=True, port=5000, host='0.0.0.0')
