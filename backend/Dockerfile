FROM python:3.11-slim

WORKDIR /srv

# Install system dependencies if needed (e.g. gcc for some packages)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libc6-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend directories
COPY app ./app
COPY mabd ./mabd
COPY main.py ./

# Create directory for local uploads fallback
RUN mkdir -p uploads

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
