FROM python:3.11 as builder

RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.11-slim

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/app" \
    UVICORN_MAX_REQUEST_BODY_SIZE=30000000 \
    UVICORN_MAX_HEADERS=8192 \
    UVICORN_LIMIT_CONCURRENCY=1000 \
    UVICORN_TIMEOUT_KEEP_ALIVE=60

RUN apt-get update && apt-get install -y \
    libgomp1 \
    && echo "fs.file-max = 100000" >> /etc/sysctl.conf \
    && echo "* soft nofile 65535" >> /etc/security/limits.conf \
    && echo "* hard nofile 65535" >> /etc/security/limits.conf \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

EXPOSE 11114
CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "-w", "4", "--bind", "0.0.0.0:11114", "--keep-alive", "30", "--worker-connections", "1000", "--reload", "main:app"]