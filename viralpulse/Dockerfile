FROM python:3.11-slim

# FFmpeg é essencial para a edição de vídeo.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# O código do ViralPulse é montado/copiado como pacote `viralpulse`.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/viralpulse

ENV PYTHONUNBUFFERED=1

# Por defeito arranca o worker 24/7. Para o dashboard, ver docker-compose.
CMD ["python", "-m", "viralpulse.main", "run"]
