import os
import socket
from getpass import getpass

import requests

user = input('user name:')
password = getpass('password:')
mid_tier_uri = input('mid-tier uri:')
server = input('server name:')


def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip


host = get_ip()
port = os.getenv('FLASK_RUN_PORT')
if port is None:
    port = '5000'
print('port is ' + port)

if mid_tier_uri[-1] != '/':
    mid_tier_uri = mid_tier_uri + '/'

print('midtier ' + mid_tier_uri)
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
