#!/bin/bash
set -e

# ---------- Install dependencies ----------
sudo dnf update -y
sudo dnf install -y docker awscli
sudo systemctl enable docker
sudo systemctl start docker

# ---------- Prepare EBS Volume ----------
VOLUME_PATH="/data/mongo"
DEVICE_NAME="/dev/xvdf"

if [ ! -d "$VOLUME_PATH" ]; then
  sudo mkdir -p "$VOLUME_PATH"
fi

# Wait for device to be ready
sleep 10

if ! sudo file -s $DEVICE_NAME | grep -q ext4; then
  echo "Formatting EBS volume..."
  sudo mkfs -t ext4 $DEVICE_NAME
fi

sudo mount $DEVICE_NAME $VOLUME_PATH
sudo chown -R ec2-user:ec2-user $VOLUME_PATH

echo "$DEVICE_NAME $VOLUME_PATH ext4 defaults,nofail 0 2" | sudo tee -a /etc/fstab

# ---------- Create Docker Network ----------
DOCKER_NETWORK="mlapp-net"
if ! sudo docker network ls --format '{{.Name}}' | grep -q "^${DOCKER_NETWORK}$"; then
  echo "Creating Docker network: ${DOCKER_NETWORK}"
  sudo docker network create "${DOCKER_NETWORK}"
else
  echo "Docker network ${DOCKER_NETWORK} already exists."
fi

# ---------- Run MongoDB ----------
sudo docker run -d --restart always \
  --name mongo \
  --network ${DOCKER_NETWORK} \
  -v ${VOLUME_PATH}:/data/db \
  -p 27017:27017 \
  mongo:6

# ---------- Wait for Mongo to start ----------
sleep 10

# ---------- Fetch model service IP ----------
MODEL_SERVICE_HOST=$(aws ssm get-parameter \
  --name "/mlapp/model/PublicIP" \
  --query "Parameter.Value" \
  --output text 2>/dev/null || echo "127.0.0.1")

echo "MODEL_SERVICE_HOST resolved to: ${MODEL_SERVICE_HOST}"

# ---------- Run Backend ----------
sudo docker run -d --restart always \
  --name backend \
  --network ${DOCKER_NETWORK} \
  -p 80:80 \
  -e "MONGO_URI=mongodb://mongo:27017/mlapp" \
  -e "MODEL_SERVICE_HOST=${MODEL_SERVICE_HOST}" \
  -e "MODEL_SERVICE_PORT=80" \
  viriyadhika/disaster-classification-mscac:latest
