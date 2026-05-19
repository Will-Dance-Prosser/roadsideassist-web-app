#!/bin/bash
set -e

echo 'Running database migrations...'
flask db upgrade

echo 'Seeding demo users...'
flask seed-demo-users

echo 'Seeding demo MDM data...'
flask seed-demo-mdm

echo 'Starting gunicorn...'
exec gunicorn wsgi:app
