release: flask db upgrade && flask seed-demo-users && flask seed-demo-mdm
web: gunicorn wsgi:app