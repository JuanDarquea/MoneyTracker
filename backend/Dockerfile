# Use Python 3.12 slim image (production-ready, smaller than full image)
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies (PostgreSQL client for debugging, curl for health checks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (Docker layer caching — requirements rarely change)
COPY backend/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini .

# Expose port 8000 (FastAPI default)
EXPOSE 8000

# Health check (optional but recommended for Render)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Run Uvicorn server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
