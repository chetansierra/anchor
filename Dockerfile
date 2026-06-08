# Hosting skeleton — deploy-ready image for Railway / Fly.io / Render.
FROM python:3.13-slim

WORKDIR /app

# Install deps first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code + both seeded corpora (Nimbus support KB + the services KB).
COPY app ./app
COPY scripts ./scripts
COPY data/kb ./data/kb
COPY data/services_kb ./data/services_kb

# Build both indexes at image-build time so /chat and /consult work on first boot.
RUN python -m scripts.ingest_cli

EXPOSE 8000
# Hosts inject $PORT; default to 8000 locally.
CMD ["sh", "-c", "python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
