import json
import os
from clockbridgeconfig import Config
from flask import Flask, Response, request

file_path = os.environ.get('CLOCKBRIDGE_CONFIG_PATH')
if not file_path:
    file_path = '/opt/clockbridge/config.yaml'

app = Flask(__name__)
config = Config(file_path)

@app.route("/webhook/clockify", methods = ['POST'])
def webhook():
    try:
        payload = json.loads(request.data)
        return payload
    except:
        return Response("Malformed request body", 400)

if __name__ == '__main__':
   app.run(debug=True)