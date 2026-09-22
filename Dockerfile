FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 APP_ENV=production
WORKDIR /app
# OpenCV/RapidOCR runtime libraries; CPU PyTorch avoids GPU runtime downloads.
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
COPY requirements.lock.txt ./
RUN pip install torch==2.6.0 --index-url https://download.pytorch.org/whl/cpu && pip install -r requirements.lock.txt
COPY backend ./backend
COPY scripts ./scripts
COPY data/manuals/manifest.json ./data/manuals/manifest.json
COPY data/equipment_catalog.json ./data/equipment_catalog.json
RUN mkdir -p data/processed data/uploads
CMD ["python", "scripts/start_backend.py"]
