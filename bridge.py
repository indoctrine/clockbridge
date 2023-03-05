import clockifysdk as cs
import os

token = os.environ['CLOCKIFY_API_KEY']
conn = cs.Connection(token)

workspaceIds = conn.get_workspace_id("Beck's Hobbies")
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
        print(project['name'])