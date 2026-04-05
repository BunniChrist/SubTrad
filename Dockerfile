FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg curl unzip nodejs npm && rm -rf /var/lib/apt/lists/*

# Install deno (required by yt-dlp for YouTube JS extraction)
RUN curl -fsSL https://deno.land/install.sh | DENO_INSTALL=/usr/local sh

# Install Codex CLI (optional translation backend)
RUN npm install -g @openai/codex

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ backend/
COPY entrypoint.sh .
RUN mkdir -p data models && chmod +x entrypoint.sh

ARG GIT_COMMIT_SHA=unknown
ENV PYTHONUNBUFFERED=1
ENV GIT_COMMIT_SHA=${GIT_COMMIT_SHA}
ENV HF_HOME=/app/models

EXPOSE 8010

CMD ["./entrypoint.sh"]
