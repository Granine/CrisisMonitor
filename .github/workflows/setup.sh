#!/bin/bash

sudo apt update -y
sudo apt install -y docker.io
sudo systemctl enable docker
sudo systemctl start docker
sudo docker run -d -p 80:80 viriyadhika/disaster-classification-mscac:latest
