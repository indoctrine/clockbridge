import clockifysdk as cs
import os
import os.path
from datetime import datetime, timedelta
from pprint import pprint
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# The ID and range of a sample spreadsheet.
SPREADSHEET_ID = '1F0l7fuqEO8jvGXu0yaaq7jvrGgqubYS3iCwjgXSkuiY'
# Possibly make this dynamic so we can get the number of days in curr year
RANGE_NAME = '2023!A2:B'

def round_time(start: str, end: str):
    startTime = datetime.strptime(start, "%Y-%m-%dT%H:%M:%SZ")
    endTime = datetime.strptime(end, "%Y-%m-%dT%H:%M:%SZ")
    
    delta = endTime - startTime
    min, sec = divmod(delta.total_seconds(), 60)
    hour, min = divmod(min, 60)

    if sec > 30:
        min += 1
    
    return timedelta(hours=hour, minutes=min)

token = os.environ['CLOCKIFY_API_KEY']
conn = cs.Connection(token)

workspaceIds = conn.get_workspace_id("Beck's Hobbies")
userId = conn.get_logged_in_user_details()['id']
workspace = cs.Workspace(workspaceIds, conn)

clients = {}
for client in workspace.get_clients():
    clients[client['id']] = client['name']
    if client['name'] == 'Drawing':
        drawingClient = cs.Client(workspace, client['name'], client['id'])

projects = workspace.get_projects()
drawingProjects = []

for project in projects:
    if project['clientId'] == drawingClient.id:
        rawTimeEntries = workspace.get_time_entries(userId, project['id'])

timeEntries = {}

for rawTimeEntry in rawTimeEntries:
    timeString = datetime.strptime(rawTimeEntry['timeInterval']['start'], "%Y-%m-%dT%H:%M:%SZ").strftime("%d/%m/%Y")
    delta = round_time(rawTimeEntry['timeInterval']['start'], rawTimeEntry['timeInterval']['end'])
    timeEntries[timeString] = timeEntries.get(timeString, timedelta(seconds=0))
    timeEntries[timeString] += delta

creds = None
# The file token.json stores the user's access and refresh tokens, and is
# created automatically when the authorization flow completes for the first
# time.
if os.path.exists('token.json'):
    creds = Credentials.from_authorized_user_file('token.json', SCOPES)
# If there are no (valid) credentials available, let the user log in.
if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file(
            'credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
    # Save the credentials for the next run
    with open('token.json', 'w') as token:
        token.write(creds.to_json())

try:
    service = build('sheets', 'v4', credentials=creds)

    # Call the Sheets API
    sheet = service.spreadsheets()
    result = sheet.values().get(spreadsheetId=SPREADSHEET_ID,
                                range=RANGE_NAME).execute()
    values = result.get('values', [])

    if not values:
        print('No data found.')

    writeValues = [ [ ] ]
    for row in values:
        if row[0] in timeEntries:
            writeValues[0].append(str(timeEntries[row[0]]))
        else:
            writeValues[0].append('00:00:00')
except HttpError as err:
    print(err)

body = {
    "majorDimension": "COLUMNS",
    'values': writeValues
}
result = service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID, range="2023!D1:D",
            valueInputOption="USER_ENTERED", body=body).execute()