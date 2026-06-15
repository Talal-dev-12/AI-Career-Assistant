FROM python:3.12-slim

# Install system dependencies needed for installing packages and headless browsers
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Run crawl4ai-setup to configure crawl4ai and install playwright browsers with system dependencies
RUN crawl4ai-setup && playwright install --with-deps chromium

# Create directories for database and logging
RUN mkdir -p data logs

# Copy the rest of the application files
COPY . .

# Expose port (Railway will override this automatically)
EXPOSE 8000

# Set environment variables to run Python in unbuffered mode
ENV PYTHONUNBUFFERED=1

# Start FastAPI server
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
