FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY app.py .
COPY templates ./templates

# Expose Flask port
EXPOSE 5000

# Ensure logs are flushed immediately
ENV PYTHONUNBUFFERED=1

# Run Flask app
CMD ["python", "app.py"]
