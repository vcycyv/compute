import os
import socket
from getpass import getpass

import requests

user = input('user name:')
password = getpass('password:')
mid_tier_uri = input('mid-tier uri:')
server = input('server name:')

host = socket.gethostname()
port = os.getenv('FLASK_RUN_PORT')
if port is None:
    port = '5000'
print('port is ' + port)

if mid_tier_uri[-1] != '/':
    mid_tier_uri = mid_tier_uri + '/'

r = requests.post(mid_tier_uri + 'auth', json={
    'username': user,
    'password': password
})
token = r.json()['token']

r = requests.post(mid_tier_uri + 'servers', json={
    'name': server,
    'host': host,
    'port': int(port),
    'health': True
}, headers={"Authorization": 'Bearer ' + token})

print('add server return status code: ' + str(r.status_code))
