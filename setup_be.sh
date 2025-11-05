#!/bin/bash

sudo apt update -y
sudo apt install -y docker.io
sudo systemctl enable docker
sudo systemctl start docker

MODEL_SERVICE_HOST=$(aws ssm get-parameter --name "/mlapp/model/PublicIP" --query "Parameter.Value" --output text 2>/dev/null)

sudo docker run -d -p 80:80 \
  -e "MONGO_URI=" \
  -e "MODEL_SERVICE_HOST=${MODEL_SERVICE_HOST}" \
  -e "MODEL_SERVICE_PORT=80" \
  viriyadhika/disaster-classification-mscac:latest