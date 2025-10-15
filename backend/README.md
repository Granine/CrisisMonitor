## Building Image

```bash
docker buildx build \
  --platform "linux/amd64,linux/arm64" \            
  -t viriyadhika/disaster-classification-mscac:latest \
  --push .
```

__To learn more: Why do I need to build for 2 OS?__


## Running Locally

#### Docker mode
`docker run -p 80:80  viriyadhika/disaster-classification-mscac`

#### Dev Mode - With AutoRefresh
`fastapi dev --port 80 app`
