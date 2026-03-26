FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ backend/
COPY frontend/ frontend/
COPY entrypoint.sh .
RUN mkdir -p data && chmod +x entrypoint.sh

ENV PYTHONUNBUFFERED=1

EXPOSE 8010

CMD ["./entrypoint.sh"]
