# Deployment Guide

## 📋 Overview
This document provides instructions for deploying QuantSandbox in production environments.

## 🗄️  Prerequisites

### Python
- Python 3.11 or higher
- Virtual environment (recommended)

### Dependencies
- pandas
- numpy
- akshare
- fastapi
- sqlalchemy
- uvicorn
- sentry-sdk

## 🚀 Quick Start

### 1. Clone the repository
```bash
git clone https://github.com/yourusername/QuantSandbox.git
cd QuantSandbox
```

### 2. Create and activate virtual environment
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scriptsctivate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment variables
Create a `.env` file in the project root:

```env
# Database configuration
DATABASE_URL=sqlite:///data/quantsandbox.sqlite3
# For PostgreSQL: DATABASE_URL=postgresql://user:password@localhost/dbname

# MX API configuration
MX_APIKEY=your-mx-api-key

# Sentry error monitoring (optional)
SENTRY_DSN=https://your-dsn@o123456.ingest.sentry.io/1234567
ENVIRONMENT=production

# FastAPI settings
HOST=0.0.0.0
PORT=8000
```

### 5. Initialize database
```bash
python -m backend.db.session init_db
```

### 6. Run the application
```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

## 🐳 Docker Deployment

### 1. Build Docker image
```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
docker build -t quant-sandbox .
```

### 2. Run Docker container
```bash
docker run -d   -p 8000:8000   -e MX_APIKEY=your-api-key   -e DATABASE_URL=sqlite:///data/quantsandbox.sqlite3   --name quant-sandbox   quant-sandbox
```

## ⚙️  Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| DATABASE_URL | sqlite:///data/quantsandbox.sqlite3 | Database connection string |
| MX_APIKEY | None | MX API key for data services |
| SENTRY_DSN | None | Sentry DSN for error monitoring |
| ENVIRONMENT | development | Environment name (development, staging, production) |
| HOST | 127.0.0.1 | Host to bind the server |
| PORT | 8000 | Port to listen on |

### Configuration File

You can also use a YAML configuration file (`config.yaml`):

```yaml
database:
  url: sqlite:///data/quantsandbox.sqlite3

mx:
  api_key: your-api-key

server:
  host: 0.0.0.0
  port: 8000
```

## 🔧  Monitoring

### Health Check
```bash
curl http://localhost:8000/api/meta
```

### Metrics
The application exposes Prometheus metrics at `/metrics`.

## 🔒  Security

### API Keys
Store sensitive information in environment variables or use a secrets manager.

### CORS
Configure CORS in `main.py`:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## 📝  Logging

The application uses structured JSON logging. Logs are output to stdout/stderr.
You can configure log level with the `LOG_LEVEL` environment variable.

## 🚑  Troubleshooting

### Common Issues

1. **Database connection errors**
   - Ensure database URL is correct
   - Check if database file has write permissions

2. **MX API errors**
   - Verify MX_APIKEY is set correctly
   - Check network connectivity to MX API

3. **Port conflicts**
   - Change port using `--port` flag or PORT environment variable

### Logs
Check application logs:
```bash
# If using Docker
docker logs quant-sandbox

# If running directly
python backend/main.py
```

## 📚  Additional Documentation

- [API Documentation](http://localhost:8000/docs)
- [Architecture Diagram](docs/architecture.md)
- [Database Schema](docs/database_schema.md)

