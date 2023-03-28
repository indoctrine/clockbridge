import os
import sys

from flask import Flask
from flask import request

def create_app():
    app = Flask(__name__)
    return app

flaskApp = create_app()

@flaskApp.route("/")
def root():
    return "Hello World"

@flaskApp.route("/webhook", methods = ['POST'])
def webhook_receive():
    # Token is sent in Clockify-Signature header - can use this to verify requests and lockdown my endpoint
    print(request.data, file=sys.stderr)
    print(request.headers.get('Clockify-Signature'), file=sys.stderr)
    return request.data