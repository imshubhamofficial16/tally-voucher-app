FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for PostgreSQL and lxml
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    libpq-dev \
    libxml2-dev \
    libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directory for raw files
RUN mkdir -p /app/raw_files

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
