FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        nginx \
        gettext-base \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

ENV PORT=8080 \
    BACKEND_PORT=8000 \
    STREAMLIT_PORT=8501 \
    API_BASE_URL=http://127.0.0.1:8000 \
    PUBLIC_API_BASE_URL=/api

RUN chmod +x /app/cloudrun_entrypoint.sh && \
    rm -f /etc/nginx/sites-enabled/default /etc/nginx/conf.d/default.conf

EXPOSE 8080

CMD ["/app/cloudrun_entrypoint.sh"]
