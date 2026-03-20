FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir aiohttp==3.11.16 edge-tts

COPY server.py .
RUN mkdir -p /app/static
COPY index.html /app/static/
COPY manifest.json /app/static/

EXPOSE 3000

CMD ["python3", "-u", "server.py"]
