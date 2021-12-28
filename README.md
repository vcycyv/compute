To start the application: (need to check ip first: ip address show)
gunicorn -w 3 -b 192.168.1.68:5000 wsgi:app

python register.py 

client needs to use ip, instead of 'localhost' to access Rest API.