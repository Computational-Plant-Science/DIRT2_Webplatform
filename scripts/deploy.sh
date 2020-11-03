#!/bin/bash

echo "Deploying ${PWD##*/}..."
host="$1"
email="$2"
compose="docker-compose -f docker-compose.prod.yml"

echo "Bringing containers down..."
$compose down --remove-orphans

echo "Fetching latest source from git..."
git fetch origin master
git checkout origin/master plantit/
git checkout origin/master scripts/
git checkout origin/master docker-compose.prod.yml

echo "Pulling new image definitions..."
$compose pull

echo "Building front end..."
cd plantit/front_end || exit
npm install
npm run build
cd ../..

echo "Collecting static files..."
$compose run plantit ./manage.py collectstatic --no-input

echo "Configuring NGINX..."
find config/nginx/conf.d/local.conf -type f -exec sed -i "s/localhost/$host/g" {} \;

echo "Configuring environment variables..."
find .env -type f -exec sed -i "s/DJANGO_API_URL=http:\/\/plantit\/apis\/v1\//DJANGO_API_URL=http:\/\/$host\/apis\/v1\//g" {} \;
find .env -type f -exec sed -i "s/DJANGO_DEBUG=True/DJANGO_DEBUG=False/g" {} \;
find .env -type f -exec sed -i "s/DJANGO_SECURE_SSL_REDIRECT=False/DJANGO_SECURE_SSL_REDIRECT=True/g" {} \;
find .env -type f -exec sed -i "s/DJANGO_SESSION_COOKIE_SECURE=False/DJANGO_SESSION_COOKIE_SECURE=True/g" {} \;
find .env -type f -exec sed -i "s/DJANGO_CSRF_COOKIE_SECURE=False/DJANGO_CSRF_COOKIE_SECURE=True/g" {} \;
find .env -type f -exec sed -i "s/NODE_ENV=development/NODE_ENV=production/g" {} \;

echo "Bringing containers up..."
$compose up -d --quiet-pull

echo "Running migrations..."
$compose exec plantit python manage.py makemigrations
$compose exec plantit python manage.py migrate

echo "Configuring sandbox container deployment target..."
$compose exec plantit /bin/bash /code/scripts/configure-sandbox.sh
if [ ! -d config/ssh ]; then
  mkdir config/ssh
fi
if [ ! -f config/ssh/known_hosts ]; then
  touch config/ssh/known_hosts
  $compose exec plantit bash -c "ssh-keyscan -H sandbox >> /code/config/ssh/known_hosts"
fi
if [ ! -f config/ssh/id_rsa.pub ]; then
  ssh-keygen -b 2048 -t rsa -f config/ssh/id_rsa -N ""
fi
$compose exec plantit bash -c "/code/scripts/ssh-copy-id.expect"
