FROM python:3.12-slim
WORKDIR /srv/api
# git : pour lire tes dépôts GitHub dans la bibliothèque
# tesseract + poppler : lecture des scans (OCR) dans la bibliothèque et les pièces jointes
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates tesseract-ocr tesseract-ocr-fra tesseract-ocr-eng poppler-utils && rm -rf /var/lib/apt/lists/*
COPY api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY api/app ./app
COPY web /srv/web
ARG ATOM_VERSION=dev
ENV ATOM_VERSION=${ATOM_VERSION} \
    ATOM_WEB=/srv/web \
    ATOM_DB=/data/atom.db \
    PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
