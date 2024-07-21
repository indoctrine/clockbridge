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

        #print(json.dumps(upstream_payload))
        r = requests.post(f"{config.elastic_creds['url']}{index_name}/_doc/?pretty",
                          data=json.dumps(upstream_payload),
                          auth=(config.elastic_creds['username'], config.elastic_creds['password'].decode()),
                          verify=config.elastic_creds['insecure']
                    )
        
        #pl = '{"description": "", "id": "643fa48b72a260677214669c", "project": {"clientId": "6422ad8ae7fbad41eb72e012", "clientName": "Drawing", "name": "Studies"}, "projectId": "6422ad91a7a47f42ecaca626", "timeInterval": {"duration": 3600, "end": "2023-04-19T08:21:00+0000", "start": "2023-04-19T07:21:00+0000"}, "@timestamp": "2024-07-21T21:26:40+1000"}'
        #r = requests.post("https://elastic.homelab.bsdgirl.net:9200/test_index/_doc/?pretty", data=pl, auth="elastic:952n3gYiUbE967m6u0MB2WvY", verify=False)
        print(r)
        return r.content

    except:
        return Response(503)

if __name__ == "__main__":
    app.run(debug=True, port=5000, host='0.0.0.0')
