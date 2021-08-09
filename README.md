To start the application:
gunicorn -w 3 -b 192.168.1.68:5000 wsgi:app