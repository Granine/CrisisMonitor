#!/bin/bash
set -e

# ---------- Install dependencies ----------
sudo dnf update -y
sudo dnf install -y docker awscli

# ---------- Enable and start Docker ----------
sudo systemctl enable docker
sudo systemctl start docker

# ---------- Wait for instance profile credentials ----------
sleep 10

# ---------- Fetch the model service IP from SSM (fallback to localhost) ----------
MODEL_SERVICE_HOST=$(aws ssm get-parameter \
  --name "/mlapp/model/PublicIP" \
  --query "Parameter.Value" \
  --output text 2>/dev/null || echo "127.0.0.1")

echo "MODEL_SERVICE_HOST resolved to: ${MODEL_SERVICE_HOST}"

# ---------- Run container ----------
sudo docker run -d --restart always -p 80:80 \
  -e "MONGO_URI=mongodb://root:example@mongodb-0.mongodb-svc.mlapp.svc.cluster.local:27017/?authSource=admin" \
  -e "MODEL_SERVICE_HOST=${MODEL_SERVICE_HOST}" \
  -e "MODEL_SERVICE_PORT=80" \
  viriyadhika/disaster-classification-mscac:latest