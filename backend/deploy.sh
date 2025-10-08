RESOURCE_GROUP="disaster-classification-mscac_group"
LOCATION="northcentralus"
PLAN_NAME="disasterclassification"
WEBAPP_NAME="disaster-classify-web"
IMAGE_NAME="viriyadhika/disaster-classification-mscac:latest"
SKU="F1"          # App Service plan tier (B1 = Basic), (F1 = Free)
PORT="80"         # Container exposed port
SLOT="disasterclassificationslot"

# ---- CREATE RESOURCE GROUP ----
echo "Creating resource group: $RESOURCE_GROUP ..."
az group create \
  --name "$RESOURCE_GROUP" \
  --location "$LOCATION"

# ---- CREATE APP SERVICE PLAN ----
echo "Creating App Service plan: $PLAN_NAME ..."
az appservice plan create \
  --name "$PLAN_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --is-linux \
  --sku "$SKU"

# ---- CREATE WEB APP ----
echo "Creating Web App: $WEBAPP_NAME ..."
az webapp create \
  --resource-group "$RESOURCE_GROUP" \
  --plan "$PLAN_NAME" \
  --name "$WEBAPP_NAME" \
  --container-image-name "$IMAGE_NAME"

# ---- SET APP SETTINGS ----
echo "Setting environment variables ..."
az webapp config appsettings set \
  --resource-group "$RESOURCE_GROUP" \
  --name "$WEBAPP_NAME" \
  --settings PORT="$PORT"

# ---- SHOW DEPLOYMENT INFO ----
echo "Deployment complete!"
az webapp show \
  --resource-group "$RESOURCE_GROUP" \
  --name "$WEBAPP_NAME" \
  --query "{url: defaultHostName, status: state}"