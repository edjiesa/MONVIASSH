# Dockerfile for Linux SSH Server Monitoring Dashboard
FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=3000
ENV HOST=0.0.0.0
ENV DATA_DIR=/app/data

WORKDIR /app

# Install minimal system dependencies for cryptography and OpenSSH utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    openssh-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY app/ ./app/

# Create persistent data directory
RUN mkdir -p /app/data

# Expose web port
EXPOSE 3000

# Health check to ensure FastAPI is responding
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:3000/api/stats/overview || exit 1

# Start the monitoring server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "3000"]
