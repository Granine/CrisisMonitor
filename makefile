AWS_REGION ?= us-east-1
AWS_ACCOUNT_ID ?= $(shell aws sts get-caller-identity --query Account --output text 2>/dev/null)
ECR_URI := $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com
NAMESPACE ?= mlapp

.PHONY: ecr-login build push images apply kube-secrets clean

ecr-login:
	aws ecr get-login-password --region $(AWS_REGION) | \
	docker login --username AWS --password-stdin $(ECR_URI)

build:
	docker buildx create --use --name xbuilder >/dev/null 2>&1 || true
	docker buildx build --platform linux/amd64 -t $(ECR_URI)/backend:latest ./backend --push
	docker buildx build --platform linux/amd64 -t $(ECR_URI)/model:latest   ./model   --push

images: ecr-login build

kube-secrets:
	@echo "Creating app-secrets from env MONGO_ROOT_USERNAME/MONGO_ROOT_PASSWORD..."
	@python3 - <<'PY' | bash
import os, urllib.parse
u=os.environ.get("MONGO_ROOT_USERNAME","root")
p=os.environ.get("MONGO_ROOT_PASSWORD","changeme!")
enc=urllib.parse.quote(p,safe="")
ns=os.environ.get("NAMESPACE","mlapp")
uri=f"mongodb://{u}:{enc}@mongodb-0.mongodb-svc.{ns}.svc.cluster.local:27017/?authSource=admin"
print(f'kubectl -n {ns} create secret generic app-secrets --from-literal=MONGO_ROOT_USERNAME="{u}" --from-literal=MONGO_ROOT_PASSWORD="{p}" --from-literal=MONGO_URI="{uri}" --dry-run=client -o yaml | kubectl apply -f -')
PY

apply:
	kubectl apply -f k8s/00-namespace.yaml
	kubectl annotate sc gp3 storageclass.kubernetes.io/is-default-class=true --overwrite || true
	sed -i "s~IMAGE_ECR_URI_MODEL~$(ECR_URI)/model:latest~g" k8s/10-model-deployment.yaml
	sed -i "s~IMAGE_ECR_URI_BACKEND~$(ECR_URI)/backend:latest~g" k8s/20-backend-deployment.yaml
	kubectl apply -n $(NAMESPACE) -f k8s/01-configmap.yaml
	$(MAKE) kube-secrets
	kubectl apply -n $(NAMESPACE) -f k8s/30-mongodb-statefulset.yaml
	kubectl apply -n $(NAMESPACE) -f k8s/31-mongodb-service.yaml
	kubectl apply -n $(NAMESPACE) -f k8s/10-model-deployment.yaml
	kubectl apply -n $(NAMESPACE) -f k8s/11-model-service.yaml
	kubectl apply -n $(NAMESPACE) -f k8s/20-backend-deployment.yaml
	kubectl apply -n $(NAMESPACE) -f k8s/21-backend-service.yaml

clean:
	kubectl delete ns $(NAMESPACE) --ignore-not-found
