#!/bin/bash

nocache=0
useprod=0

while getopts 'np' opt; do
    case $opt in
        n) nocache=1 ;;
        p) useprod=1 ;;
        *) echo 'Error in command line parsing' >&2
           exit 1
    esac
done
shift "$(( OPTIND - 1 ))"

if [[ "$useprod" -eq 0 ]]; then
  echo "Bootstrapping ${PWD##*/} for development..."
  compose="docker-compose -f docker-compose.dev.yml"
else
  echo "Bootstrapping ${PWD##*/} for production..."
  compose="docker-compose -f docker-compose.prod.yml"
fi

echo "Bringing containers down..."
$compose down --remove-orphans

env_file=".env"
echo "Checking for environment variable file '$env_file'..."
if [ ! -f $env_file ]; then
  echo "Environment variable file '$env_file' does not exist. Creating it..."
  chmod +x dev/create-env-file.sh
  ./dev/create-env-file.sh
else
  echo "Environment variable file '$env_file' already exists. Continuing..."
fi

echo "Building front end..."
cd plantit/front_end || exit
npm install
npm run build
cd ../..

if [[ "$nocache" -eq 0 ]]; then
  echo "Building containers..."
  $compose build "$@"
else
  echo "Building containers with option '--no-cache'..."
  $compose build "$@" --no-cache
fi
$compose up -d plantit

echo "Running migrations..."
$compose exec plantit python manage.py makemigrations
$compose exec plantit python manage.py migrate

echo "Creating superuser..."
admin_password=$(cut -d '=' -f 2 <<< "$(grep "DJANGO_ADMIN_PASSWORD" "$env_file")" )
admin_username=$(cut -d '=' -f 2 <<< "$(grep "DJANGO_ADMIN_USERNAME" "$env_file")" )
$compose exec plantit /code/dev/configure-superuser.sh -u "$admin_username" -p "$admin_password" -e "admin@example.com"

echo "Configuring sandbox deployment target container..."
$compose up -d sandbox
$compose exec plantit /bin/bash /root/configure-sandbox.sh
if [ -f config/ssh/known_hosts ]; then
  touch config/ssh/known_hosts
fi
$compose exec plantit bash -c "ssh-keyscan -H sandbox >> /code/config/ssh/known_hosts"
if [ ! -f config/ssh/id_rsa.pub ]; then
  ssh-keygen -b 2048 -t rsa -f config/ssh/id_rsa -N ""
fi
$compose exec plantit bash -c "/code/dev/ssh-copy-id.expect"

if [[ "$useprod" -eq 0 ]]; then
  echo "Configuring iRODS container..."
  $compose up -d irods
  $compose exec sandbox /bin/bash /root/wait-for-it.sh irods:1247 -- /root/configure-irods.sh
fi

echo "Stopping containers..."
$compose stop