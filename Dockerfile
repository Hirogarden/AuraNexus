# Base Python application image
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt requirements-optional.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r requirements-optional.txt || true

# Copy application code
COPY src/ ./src/
COPY app/ ./app/
COPY config/ ./config/
COPY aura_nexus_app.py ./

# Create data directories
RUN mkdir -p /app/data /app/logs

# Expose default ports
EXPOSE 8000 7860

# Run the main application
CMD ["python", "aura_nexus_app.py"]
