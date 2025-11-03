FROM python:3.11-slim

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    ca-certificates \
    libgomp1 \
    libstdc++6 \
    libatomic1 \
 && rm -rf /var/lib/apt/lists/*

# Upgrade pip tooling
RUN python -m pip install --upgrade pip setuptools wheel

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Install CPU-only PyTorch from PyTorch's CPU wheel index
# Change the version if you want a different torch version.
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.9.0

COPY app.py .
COPY services.py .

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]


