import sys
import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

class GoogleSheet:
    def __init__(self, scope: list, id: str, credsPath: str='credentials.json'):
        # If modifying scopes, delete the file at tokenPath
        self.scopes = scope
        self.spreadsheetId = id
        self.creds = None
        self.credsPath = credsPath

    def authenticate(self, tokenPath: str):
        try:
            self.tokenPath = tokenPath
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

    def get_sheet_values(self, cellRange: str):
        result = self.sheet.values().get(spreadsheetId=self.spreadsheetId,
                                range=cellRange).execute()
        values = result.get('values', [])

        if not values:
            print('No data found.')

        return values
    
    def set_sheet_values(self, cellRange: str, dimension: str, values: list):
        body = {
            "majorDimension": dimension,
            'values': values
        }

        result = self.sheet.values().update(
                    spreadsheetId=self.spreadsheetId, range=cellRange,
                    valueInputOption="USER_ENTERED", body=body).execute()
        
        return result
        
    def build_service(self):
        try:
            service = build('sheets', 'v4', credentials=self.creds)
            self.sheet = service.spreadsheets()          
            return True
        except Exception as e:
            print(e, file=sys.stderr)
