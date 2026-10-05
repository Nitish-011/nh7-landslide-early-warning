# Use official lightweight Python image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    HOST=0.0.0.0

WORKDIR /app

# Install curl for health check probing
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application directories and files
COPY app/ ./app/
COPY data/ ./data/
COPY geojson/ ./geojson/
COPY model/ ./model/
COPY outputs/ ./outputs/
COPY run.py reset_db.py ./

# Ensure runtime directories exist
RUN mkdir -p /app/data /app/logs

EXPOSE 8000

# Health check probe against /health (sub-second health check)
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# CRITICAL: Run uvicorn with a SINGLE worker (--workers 1) so the in-process
# APScheduler background weather polling job is not duplicated across multiple worker processes.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
