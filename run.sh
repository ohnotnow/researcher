#!/bin/bash
set -e

# Check if the container is already running
if docker ps --format '{{.Names}}' | grep -q '^researcher$'; then
  echo "Container is already running"
  exit 1
fi

docker build -t researcher .

# put your various environment variables in a file named .env
docker run -it --rm  --env-file=.env researcher

