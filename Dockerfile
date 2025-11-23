FROM python:3.11-slim

WORKDIR /app

# Minimal system dependencies (curl for debugging/health checks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1

# Copy only what we need to install and run
COPY pyproject.toml README.md ./
COPY src ./src
COPY static ./static

RUN pip install --no-cache-dir -U pip && \
    pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "src.api_server:app", "--host", "0.0.0.0", "--port", "8000"]

# docker run --rm -p 8000:8000 \
#   -e AWS_PROFILE=AWSAdministratorAccess-112393354239 \
#   -e AWS_REGION=us-east-1 \
#   -v ~/.aws:/root/.aws:ro \
#   fredgpt-backend
