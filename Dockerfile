# Railway backend: FastAPI + crawl4ai (Playwright / Chromium)
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

# 1) Python deps first (better layer caching)
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# 2) Chromium + all system libs Playwright needs
RUN python -m playwright install --with-deps chromium

# 3) App code
COPY . .

# Railway injects $PORT at runtime
ENV PORT=8000
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}"]
