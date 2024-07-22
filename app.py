import os
from clockbridgeconfig import Config
import webhook
from flask import Flask, Response, request

# Kludge libraries
import requests
from datetime import datetime, timezone
import json

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
        payload = hook.verify_incoming_webhook(request.headers, request.data)
        if not payload:
            return Response("Unauthorized", 403)
        duration = payload.timeInterval['duration']

    except ValueError:
        return Response("Malformed request body", 400)

    try:
        # From here on out is just kludge code to make this work because I'm bored of manually entering data
        now = datetime.now().astimezone()
        
        index_name = f"test-{now.strftime('%Y-%m')}"
        ts = { "@timestamp": now.strftime('%Y-%m-%dT%H:%M:%S%z') }
        upstream_payload = dict(payload)
        upstream_payload.update(ts)

        pwd = config.elastic_creds['password'].decode().strip()
        
        r = requests.post(f"{config.elastic_creds['url']}{index_name}/_doc/?pretty",
                          data=json.dumps(upstream_payload),
                          auth=(config.elastic_creds['username'], pwd),
                          verify=not config.elastic_creds['insecure'],
                          headers={"Content-Type": "application/json"}
                    )

        return r.content

    except:
        return Response(503)

if __name__ == "__main__":
    app.run(debug=True, port=5000, host='0.0.0.0')
