FROM python:3.12-slim
WORKDIR /srv/api
# git : pour lire tes dépôts GitHub dans la bibliothèque
# tesseract + poppler : lecture des scans (OCR) dans la bibliothèque et les pièces jointes
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates tesseract-ocr tesseract-ocr-fra tesseract-ocr-eng poppler-utils && rm -rf /var/lib/apt/lists/*
COPY api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY api/app ./app
COPY web /srv/web
COPY api/entrypoint.sh /usr/local/bin/atom-entrypoint
# Utilisateur non privilégié : Atom ne tourne pas en root dans le conteneur.
RUN useradd --create-home --uid 1000 atom && mkdir -p /data /backups && chown atom:atom /data /backups \
    && chmod +x /usr/local/bin/atom-entrypoint
ARG ATOM_VERSION=dev
ENV ATOM_VERSION=${ATOM_VERSION} \
    ATOM_WEB=/srv/web \
    ATOM_DB=/data/atom.db \
    PYTHONUNBUFFERED=1
EXPOSE 8000
ENTRYPOINT ["atom-entrypoint"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
