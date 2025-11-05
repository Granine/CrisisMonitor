#!/bin/bash
set -euo pipefail

# ---------- Config ----------
VOLUME_PATH="/data/mongo"
DEVICE_NAME="/dev/xvdf"
DOCKER_NETWORK="mlapp-net"
MONGO_CONTAINER="mongo"
BACKEND_CONTAINER="backend"
MONGO_IMAGE="mongo:6"
BACKEND_IMAGE="viriyadhika/disaster-classification-mscac:latest"

echo "[INFO] Starting setup..."

# ---------- Install dependencies ----------
sudo dnf update -y
sudo dnf install -y docker awscli jq
sudo systemctl enable docker
sudo systemctl start docker

# ---------- Prepare EBS Volume ----------
echo "[INFO] Preparing EBS volume..."
sudo mkdir -p "$VOLUME_PATH"

# Wait for device to be ready
sleep 10

echo "[INFO] Waiting for EBS device $DEVICE_NAME..."
for i in {1..12}; do
  if lsblk | grep -q "$(basename $DEVICE_NAME)"; then
    echo "[INFO] $DEVICE_NAME detected."
    break
  fi
  echo "[WARN] Device not ready yet, sleeping..."
  sleep 5
done

if ! lsblk | grep -q "$(basename $DEVICE_NAME)"; then
  echo "[ERROR] $DEVICE_NAME not found after waiting. Exiting."
  exit 1
fi

if ! sudo file -s "$DEVICE_NAME" | grep -q ext4; then
  echo "[INFO] Formatting $DEVICE_NAME as ext4..."
  sudo mkfs -t ext4 "$DEVICE_NAME"
else
  echo "[INFO] $DEVICE_NAME already formatted."
fi

# Mount volume (skip if already mounted)
if ! mount | grep -q "$VOLUME_PATH"; then
  echo "[INFO] Mounting $DEVICE_NAME to $VOLUME_PATH..."
  sudo mount "$DEVICE_NAME" "$VOLUME_PATH"
  echo "$DEVICE_NAME $VOLUME_PATH ext4 defaults,nofail 0 2" | sudo tee -a /etc/fstab
else
  echo "[INFO] Volume already mounted."
fi

sudo chown -R ec2-user:ec2-user "$VOLUME_PATH"

# ---------- Create Docker Network ----------
if ! sudo docker network ls | grep -q "$DOCKER_NETWORK"; then
  echo "[INFO] Creating Docker network $DOCKER_NETWORK..."
  sudo docker network create "$DOCKER_NETWORK"
else
  echo "[INFO] Docker network $DOCKER_NETWORK already exists."
fi

# ---------- Run MongoDB ----------
if sudo docker ps -a --format '{{.Names}}' | grep -q "^${MONGO_CONTAINER}$"; then
  echo "[INFO] Existing MongoDB container found. Restarting..."
  sudo docker restart "$MONGO_CONTAINER"
else
  echo "[INFO] Starting new MongoDB container..."
  sudo docker run -d --restart always \
    --name "$MONGO_CONTAINER" \
    --network "$DOCKER_NETWORK" \
    -v "${VOLUME_PATH}:/data/db" \
    "$MONGO_IMAGE" --bind_ip_all
fi

# ---------- Wait for Mongo to start ----------
echo "[INFO] Waiting for MongoDB to become ready..."
sleep 10

# ---------- Fetch model service IP ----------
MODEL_SERVICE_HOST=$(aws ssm get-parameter \
  --name "/mlapp/model/PublicIP" \
  --query "Parameter.Value" \
  --output text 2>/dev/null || echo "127.0.0.1")

echo "[INFO] MODEL_SERVICE_HOST resolved to: ${MODEL_SERVICE_HOST}"

# ---------- Run Backend ----------
if sudo docker ps -a --format '{{.Names}}' | grep -q "^${BACKEND_CONTAINER}$"; then
  echo "[INFO] Existing backend container found. Recreating..."
  sudo docker rm -f "$BACKEND_CONTAINER"
fi

echo "[INFO] Starting backend container..."
sudo docker run -d --restart always \
  --name "$BACKEND_CONTAINER" \
  --network "$DOCKER_NETWORK" \
  -p 80:80 \
  -e "MONGO_URI=mongodb://${MONGO_CONTAINER}:27017/mlapp" \
  -e "MODEL_SERVICE_HOST=${MODEL_SERVICE_HOST}" \
  -e "MODEL_SERVICE_PORT=80" \
  "$BACKEND_IMAGE"

echo "[SUCCESS] Backend and MongoDB setup complete!"
