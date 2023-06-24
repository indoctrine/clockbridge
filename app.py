import json
import clockbridge
from flask import Flask, Response, request, jsonify

app = Flask(__name__)

@app.route("/webhook/clockify", methods = ['POST'])
def webhook():
    try:
        payload = json.loads(request.data)
        return payload
    except:
        return Response("Malformed request body", 400)

if __name__ == '__main__':
   app.run(debug=True)