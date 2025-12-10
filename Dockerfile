# Use Python 3.9 slim image 
FROM python:3.9-slim 
 
# Set working directory 
WORKDIR /app 
 
# Install system dependencies 
    gcc \ 
 
# Copy requirements first (for better layer caching) 
COPY requirements.txt . 
RUN pip install --no-cache-dir -r requirements.txt 
 
# Copy application code 
COPY . . 
 
# Create necessary directories for cloud environment 
RUN mkdir -p /tmp/logs 
 
# Set environment variables for production 
ENV PORT=8080 
ENV PYTHONUNBUFFERED=1 
ENV DB_PATH=/tmp/signals.db 
ENV LOG_DIR=/tmp/logs 
ENV ADMIN_PASSWORD=admin123 
ENV CUSTOMER_PASSWORD=cust123 
 
# Expose the port 
EXPOSE 8080 
 
# Health check 
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \ 
 
# Run the application 
CMD ["python", "server.py"] 
