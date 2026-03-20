FROM python:3.11-slim

# yt-dlp und ffmpeg installieren
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# yt-dlp als Binary (immer aktuellste Version)
RUN curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o /usr/local/bin/yt-dlp \
    && chmod a+rx /usr/local/bin/yt-dlp

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

# Temp-Ordner fuer Downloads
RUN mkdir -p /tmp/video-analyzer

EXPOSE 3001

CMD ["python", "server.py"]
