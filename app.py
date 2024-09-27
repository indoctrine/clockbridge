import os
from clockbridgeconfig import Config
import webhook
from flask import Flask, Response, request
import sys
import logging

# Kludge libraries
import requests
import urllib3
from datetime import datetime, timezone
import json

logger = logging.getLogger(__name__)
logging.basicConfig(format='%(asctime)s [%(levelname)s] %(message)s',
                    stream=sys.stderr,level=logging.INFO)
file_path = os.environ.get('CLOCKBRIDGE_CONFIG_PATH')
if not file_path:
    file_path = os.path.join(os.getcwd(), 'config.yaml')

app = Flask(__name__)
config = Config(file_path)

@app.route("/ping", methods = ['GET'])
def ping():
    return "Pong\n"

@app.route("/webhook/clockify", methods = ['POST'])
def clockbridge():
    try:
        hook = webhook.Webhook(config)
        logging.info("Payload headers:\n %s", dict(request.headers))
        logging.info("Processing payload:\n %s", json.dumps(request.json, indent=4))
        payload = hook.verify_incoming_webhook(request.headers, request.data)
        if not payload:
            return Response("Unauthorized", 403)
    except ValueError:
        return Response("Malformed request body", 400)

    try:
        # From here on out is just kludge code to make this work because I'm bored of manually entering data
        urllib3.disable_warnings(category=urllib3.exceptions.InsecureRequestWarning)
        now = datetime.now().astimezone()
        index_name = f"test-{now.strftime('%Y-%m')}"
        payload['@timestamp'] = now.strftime('%Y-%m-%dT%H:%M:%S%z')
        pwd = config.elastic_creds['password'].decode().strip()
        
        if hook.action == "TIME_ENTRY_DELETED":
            r = delete_doc(config.elastic_creds['url'], index_name, payload['id'], config.elastic_creds['username'], pwd)

        elif hook.action == "TIME_ENTRY_UPDATED":
            r = delete_doc(config.elastic_creds['url'], index_name, payload['id'], config.elastic_creds['username'], pwd)
            r = create_doc(config.elastic_creds['url'], index_name, payload['id'], config.elastic_creds['username'], pwd, payload)
        else:
            r = create_doc(config.elastic_creds['url'], index_name, payload['id'], config.elastic_creds['username'], pwd, payload)
        return payload

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
        logging.info("Deleted from Elasticsearch:\n %s", r.content)
        return r.content
    except Exception as e:
        logging.exception("Unable to delete document from Elasticsearch\n %s", e)

def create_doc(url, index, doc_id, user, pwd, payload, verify_ssl=False):
    try:
        r = requests.post(f"{url}{index}/_create/{doc_id}",
                        data=json.dumps(payload),
                        auth=(user, pwd),
                        verify=verify_ssl,
                        headers={"Content-Type": "application/json"},
                        timeout=10
                    )
        logging.info("Created from Elasticsearch:\n %s", r.content)
        return r.content
    except Exception as e:
        logging.exception("Unable to create document in Elasticsearch\n %s", e)

if __name__ == "__main__":
    app.run(debug=True, port=5000, host='0.0.0.0')
