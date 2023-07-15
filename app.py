import json
from clockbridgeconfig import Config
from flask import Flask, Response, request

app = Flask(__name__)
config = Config('config.yaml')

@app.route("/webhook/clockify", methods = ['POST'])
def webhook():
    try:
        payload = json.loads(request.data)
        return payload
    except:
        return Response("Malformed request body", 400)

if __name__ == '__main__':
   app.run(debug=True)