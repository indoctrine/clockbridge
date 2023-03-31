import os
import sys
import json
import calendar
from datetime import datetime
from flask import Flask
from flask import Response
from flask import request
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

class GoogleSheet:
    def __init__(self, scope: list, id: str, sheetRange: str, tokenPath: str, credsPath: str='credentials.json'):
        # If modifying these scopes, delete the file token.json
        self.scopes = scope
        self.spreadsheetId = id
        self.range = sheetRange
        self.creds = None
        self.tokenPath = tokenPath
        self.credsPath = credsPath

    def authenticate(self):
        try:
            if os.path.exists(self.tokenPath):
                self.creds = Credentials.from_authorized_user_file(self.tokenPath, self.scopes)
            if not self.creds or not self.creds.valid:
                if self.creds and self.creds.expired and self.creds.refresh_token:
                    self.creds.refresh(Request())
                else:
                    self.flow = InstalledAppFlow.from_client_secrets_file(
                        'credentials.json', self.scopes)
                    self.creds = self.flow.run_local_server(port=0)
                # Save the credentials for the next run
                with open(self.tokenPath, 'w') as token:
                    token.write(self.creds.to_json())
            return True
        except Exception as e:
            print(e, file=sys.stderr)

    def get_sheet_values(self, cell_range: str or None=None):
        if cell_range is None:
            cell_range = self.range
        result = self.sheet.values().get(spreadsheetId=self.spreadsheetId,
                                range=self.range).execute()
        values = result.get('values', [])

        if not values:
            print('No data found.')

        return values
        
    def build_service(self):
        try:
            service = build('sheets', 'v4', credentials=self.creds)
            self.sheet = service.spreadsheets()          
            return True
        except Exception as e:
            print(e, file=sys.stderr)

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
    with open('webhook-secrets.json', 'r') as fp:
        secrets = json.load(fp)
        tokens = secrets['secrets']
    token = request.headers.get('Clockify-Signature')
    
    if token in tokens:
        payload = json.loads(request.data)

        if payload['project']['clientName'] == 'Drawing':
            endDate = datetime.strptime(payload['timeInterval']['end'], "%Y-%m-%dT%H:%M:%SZ")
            dayOfYear = endDate.timetuple().tm_yday
            
            # Allow for header row
            hookDateRange = f'A{dayOfYear+1}:B{dayOfYear+1}'
            sheet = GoogleSheet(scope=['https://www.googleapis.com/auth/spreadsheets'], 
                                id='1F0l7fuqEO8jvGXu0yaaq7jvrGgqubYS3iCwjgXSkuiY',
                                sheetRange=hookDateRange, 
                                tokenPath='token.json')
            sheet.authenticate()
            sheet.build_service()
            sheetValues = sheet.get_sheet_values()
            print(sheetValues)
            return payload
        else:
            return Response("Nothing to process", 200)
    else:
        return Response("Authentication required", 401)
    
#def get_sheet_values():
