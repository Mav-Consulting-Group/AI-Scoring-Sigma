# Start with Python 3.13 base image
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Install system dependencies for pip + build
RUN apt-get update && apt-get install -y gcc curl && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the whole app
COPY . .

# Environment variables for Render
ENV PYTHONUNBUFFERED=1 \
    PORT=8000

# Expose port
EXPOSE 8000

# Start FastAPI app using Uvicorn
CMD ["sh","-c","uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
