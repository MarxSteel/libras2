FROM python:3.12-slim

# ffmpeg pro concatenar vídeos + geração de GIF
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        git \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# deps primeiro (cache de layer)
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .[all] || pip install --no-cache-dir .

COPY src/ ./src/

ENV PYTHONUNBUFFERED=1 \
    VLIBRAS_DATA_DIR=/data/vlibrasil \
    VLIBRAS_CACHE_DIR=/data/cache

EXPOSE 8088

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://127.0.0.1:8088/health', timeout=3).raise_for_status()" || exit 1

CMD ["uvicorn", "service.main:app", "--host", "0.0.0.0", "--port", "8088", "--workers", "2"]
