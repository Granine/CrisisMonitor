FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 libstdc++6 libatomic1 \
 && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --upgrade pip setuptools wheel

COPY requirements.txt .


RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY services.py .

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]


