import clockifysdk as cs
import os
from datetime import datetime, timedelta
from pprint import pprint

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
    timeString = datetime.strptime(rawTimeEntry['timeInterval']['start'], "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d")
    delta = round_time(rawTimeEntry['timeInterval']['start'], rawTimeEntry['timeInterval']['end'])
    timeEntries[timeString] = timeEntries.get(timeString, timedelta(seconds=0))
    timeEntries[timeString] += delta