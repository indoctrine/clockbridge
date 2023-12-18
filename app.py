import json
import os
from clockbridgeconfig import Config
import clockbridge
from flask import Flask, Response, request

file_path = os.environ.get('CLOCKBRIDGE_CONFIG_PATH')
if not file_path:
    file_path = os.path.join(os.getcwd(), 'config.yaml')

app = Flask(__name__)
config = Config(file_path)

@app.route("/webhook/ping", methods = ['GET'])
def ping():
	return "Pong\n"

@app.route("/webhook/clockify", methods = ['POST'])
def webhook():
    try:
        bridge = clockbridge.Clockbridge(config)
        verified = bridge.verify_incoming_webhook(request.headers, request.data)
        if verified:
            return verified
        else:
            return Response("Unauthorized", 403)
    except Exception as e:
        return Response(f"{e}", 400)
        return Response("Malformed request body", 400)

if __name__ == "__main__":
	app.run(debug=True, port=5000, host='0.0.0.0')
