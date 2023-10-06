import json
import os
from clockbridgeconfig import Config
import clockbridge
from flask import Flask, Response, request

file_path = os.environ.get('CLOCKBRIDGE_CONFIG_PATH')
if not file_path:
    file_path = '/opt/clockbridge/config.yaml'

app = Flask(__name__)
config = Config(file_path)

@app.route("/webhook/clockify", methods = ['POST'])
def webhook():
    try:
        bridge = clockbridge.Clockbridge()
        verified = bridge.verify_webhook_signature(request.headers, config)
        payload = json.loads(request.data)
        if verified:
            return payload
        else:
            return Response("Unauthorized", 403)
    except:
        return Response("Malformed request body", 400)

if __name__ == '__main__':
   app.run(debug=True, host="0.0.0.0")
