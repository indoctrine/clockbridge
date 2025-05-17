"""
AUTHOR:     Beck D.
DATE:       2023-
PURPOSE:    The main Flask application file
"""

import os
import sys
import logging
import json
from datetime import datetime
from queue import Queue
from clockbridgeconfig import Config
from elastic import Elastic
import webhook
from flask import Flask, Response, request

file_path = os.environ.get('CLOCKBRIDGE_CONFIG_PATH')
if not file_path:
    file_path = os.path.join(os.getcwd(), 'config.yaml')

app = Flask(__name__)
config = Config(file_path)
logging.info("Configuration loaded from %s, logging at %s level", file_path, config.log_level)
job_queue = Queue(maxsize=100)
es = Elastic(config.elastic_creds)

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
        if request.json['timeInterval']['end'] is None:
            return Response("Payload not ready for upload", 409)

        payload = hook.verify_incoming_webhook(request)
        if not payload:
            return Response("Unauthorized", 403)

        now = datetime.now().astimezone()
        payload['@timestamp'] = now.strftime('%Y-%m-%dT%H:%M:%S%z')
        job_queue.put(payload)

    except ValueError:
        return Response("Malformed request body", 400)

    try:
        if es.health_check():
            logger.info("Elasticsearch endpoint up, pushing data...")
            for job in range(job_queue.qsize()):
                data = job_queue.get(job)
                if hook.action == "TIME_ENTRY_DELETED":
                    r = es.delete_doc(data)
                elif hook.action == "TIME_ENTRY_UPDATED":
                    r = es.update_doc(data)
                else:
                    r = es.create_doc(data)

                if not r:
                    # If the task above doesn't complete successfully, put the job back in the queue
                    job_queue.put(data)
            return Response("Data successfully inserted into Elasticsearch", 200)
    except Exception:
        return Response(503)

if __name__ == "__main__":
    app.run(debug=True, port=5000, host='0.0.0.0')
