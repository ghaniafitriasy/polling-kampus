# Image backend Python (tanpa framework, hanya pustaka standar)
FROM python:3.12-slim

# Log Python langsung tampil di "docker logs"
ENV PYTHONUNBUFFERED=1 \
    DATA_DIR=/var/lib/backend_data \
    PORT=5000

WORKDIR /app

# Folder data. Saat container dijalankan, folder ini ditimpa oleh Named Volume.
RUN mkdir -p /var/lib/backend_data

COPY app.py .

EXPOSE 5000

CMD ["python", "app.py"]
