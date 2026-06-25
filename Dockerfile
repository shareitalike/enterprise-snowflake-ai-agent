FROM python:3.10-slim

WORKDIR /app

# Install system dependencies for Snowflake connector
RUN apt-get update && apt-get install -y \
    build-essential \
    libssl-dev \
    libffi-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose ports for FastAPI (8000) and Streamlit (8501)
EXPOSE 8000
EXPOSE 8501

# Default command runs the FastAPI server
# You can override this in docker-compose or run command for Streamlit
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
