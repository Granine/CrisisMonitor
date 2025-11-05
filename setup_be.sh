#!/bin/bash

sudo apt update -y
sudo apt install -y docker.io
sudo systemctl enable docker
sudo systemctl start docker

MODEL_SERVICE_HOST=$(aws ssm get-parameter --name "/mlapp/model/PublicIP" --query "Parameter.Value" --output text 2>/dev/null)
MODEL_SERVICE_PORT="80"

sudo docker run -d -p 80:80 \
  -e MONGO_URI="" \
  -e MODEL_SERVICE_HOST="model-svc" \
  -e MODEL_SERVICE_PORT="80" \
  viriyadhika/disaster-classification-mscac:latest