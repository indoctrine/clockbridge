import sys
import os
from google.auth.transport.requests import Request
#from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

class GoogleSheet:
    def __init__(self, scope: list, id: str):
        self.scopes = scope
        self.spreadsheetId = id
        self.creds = None

    def authenticate(self, credsPath: str):
        try:
            self.credsPath = credsPath
            if os.path.exists(self.credsPath):
                self.creds = service_account.Credentials.from_service_account_file(self.credsPath, scopes=self.scopes)
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
