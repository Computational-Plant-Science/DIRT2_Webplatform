#!/bin/sh

eval "$(ssh-agent -s)" # Start ssh-agent cache
chmod 600 id_rsa # Allow read access to the private key
ssh-add id_rsa # Add the private key to SSH

ssh -o $SSH_USER@$SSH_HOST -p $SSH_PORT <<EOF
  cd $SSH_DIRECTORY
  docker-compose -f docker-compose.yml -f docker-compose.prod.yml down
EOF

git config --global push.default matching
git remote add deploy ssh://$SSH_USER@$SSH_HOST:$SSH_PORT$SSH_DIRECTORY
git push deploy master

ssh -o $SSH_USER@$SSH_HOST -p $SSH_PORT <<EOF
  cd $SSH_DIRECTORY
  ./dev/post-deploy.sh $SSH_HOST
EOF