# Deployment

Deploying Serv applications to production requires careful consideration of server configuration, environment setup, security, and monitoring. This guide covers everything you need to know about deploying Serv applications effectively.

## Overview

Serv deployment considerations:

1. **ASGI Servers**: Choose the right ASGI server for your needs
2. **Environment Configuration**: Manage settings across environments
3. **Containerization**: Docker and container orchestration
4. **Security**: SSL/TLS, secrets management, and security headers
5. **Performance**: Optimization and scaling strategies
6. **Monitoring**: Logging, metrics, and health checks

## ASGI Servers

Serv is an ASGI framework that integrates tightly with uvicorn. The App class must be instantiated within a running asyncio event loop, which makes uvicorn the preferred deployment option.

### Serv CLI (Recommended)

The easiest way to deploy Serv applications is using the built-in CLI commands:

```bash
# Production deployment
serv launch --host 0.0.0.0 --port 8000 --workers 4

# Development server
serv --dev launch --host 0.0.0.0 --port 8000

# Test configuration before deployment
serv launch --dry-run

# Custom configuration
serv launch --config config/production.yaml --host 0.0.0.0 --port 8000 --workers 4
```

### Uvicorn Direct Usage

**Important**: Serv's App class must be instantiated within a running asyncio event loop. This means you cannot use uvicorn's CLI directly with a pre-instantiated App object. Instead, you must use an application factory pattern:

```python
# main.py - Application factory for uvicorn
import asyncio
from serv.app import App

def create_app():
    """Application factory that creates the app within the event loop"""
    # This function will be called by uvicorn within the event loop
    app = App(
        config="config/production.yaml",
        extension_dir="./extensions",
        dev_mode=False
    )
    return app

# For uvicorn, use the factory
app = create_app
```

```bash
# Install Uvicorn
pip install uvicorn[standard]

# Use the factory function (note the lack of parentheses)
uvicorn main:app --host 0.0.0.0 --port 8000 --factory

# With workers for better performance
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4 --factory

# With SSL
uvicorn main:app --host 0.0.0.0 --port 8000 --ssl-keyfile key.pem --ssl-certfile cert.pem --factory
```

**Note**: The `--factory` flag tells uvicorn to call the function to create the app instance rather than importing a pre-created instance.

### Gunicorn with Uvicorn Workers

For production deployments, use Gunicorn with Uvicorn workers:

```bash
# Install Gunicorn
pip install gunicorn

# Run with Uvicorn workers
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000

# With configuration file
gunicorn main:app -c gunicorn.conf.py
```

**gunicorn.conf.py:**
```python
# Gunicorn configuration for production

# Server socket
bind = "0.0.0.0:8000"
backlog = 2048

# Worker processes
workers = 4
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50
preload_app = True

# Restart workers after this many requests, to help prevent memory leaks
max_requests = 1200
max_requests_jitter = 50

# Timeout for graceful workers restart
timeout = 30
keepalive = 2

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "serv_app"

# Server mechanics
daemon = False
pidfile = "/tmp/gunicorn.pid"
user = None
group = None
tmp_upload_dir = None

# SSL
keyfile = None
certfile = None
```

### Hypercorn

Alternative ASGI server with HTTP/2 support:

```bash
# Install Hypercorn
pip install hypercorn

# Basic run
hypercorn main:app --bind 0.0.0.0:8000

# With workers
hypercorn main:app --bind 0.0.0.0:8000 --workers 4

# With HTTP/2
hypercorn main:app --bind 0.0.0.0:8000 --http2
```

## Application Configuration

### Production App Setup

**main.py:**
```python
import os
from serv.app import App

def create_app():
    """Application factory for production deployment."""
    
    # Determine environment
    environment = os.getenv("ENVIRONMENT", "production")
    
    # Load appropriate configuration
    config_file = f"config/{environment}.yaml"
    
    # Create app with production settings
    app = App(
        config=config_file,
        extension_dir="./extensions",
        dev_mode=environment == "development"
    )
    
    return app

# Export the factory function for ASGI servers
app = create_app

# For development server
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        factory=True
    )
```

### Environment-Specific Configuration

**config/production.yaml:**
```yaml
site:
  name: "My Production App"
  description: "Production deployment"
  debug: false

database:
  url: "${DATABASE_URL}"
  pool_size: 20
  max_overflow: 30

redis:
  url: "${REDIS_URL}"
  max_connections: 50

security:
  secret_key: "${SECRET_KEY}"
  allowed_hosts:
    - "myapp.com"
    - "www.myapp.com"
  cors_origins:
    - "https://myapp.com"
    - "https://www.myapp.com"

logging:
  level: "INFO"
  format: "json"
  handlers:
    - "console"
    - "file"

extensions:
  - name: "auth"
    enabled: true
    config:
      session_timeout: 3600
      jwt_secret: "${JWT_SECRET}"
  
  - name: "database"
    enabled: true
    config:
      database_url: "${DATABASE_URL}"
  
  - name: "monitoring"
    enabled: true
    config:
      metrics_endpoint: "/metrics"
      health_endpoint: "/health"
```

**config/staging.yaml:**
```yaml
site:
  name: "My Staging App"
  description: "Staging environment"
  debug: true

database:
  url: "${STAGING_DATABASE_URL}"
  pool_size: 10
  max_overflow: 20

redis:
  url: "${STAGING_REDIS_URL}"
  max_connections: 25

security:
  secret_key: "${STAGING_SECRET_KEY}"
  allowed_hosts:
    - "staging.myapp.com"
  cors_origins:
    - "https://staging.myapp.com"

logging:
  level: "DEBUG"
  format: "text"
  handlers:
    - "console"

extensions:
  - name: "auth"
    enabled: true
    config:
      session_timeout: 1800
      jwt_secret: "${STAGING_JWT_SECRET}"
  
  - name: "database"
    enabled: true
    config:
      database_url: "${STAGING_DATABASE_URL}"
```

### Environment Variables

**.env.production:**
```bash
# Environment
ENVIRONMENT=production

# Database
DATABASE_URL=postgresql://user:password@db.example.com:5432/myapp
REDIS_URL=redis://redis.example.com:6379/0

# Security
SECRET_KEY=your-super-secret-key-change-this
JWT_SECRET=your-jwt-secret-key

# External Services
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=noreply@myapp.com
SMTP_PASSWORD=smtp-password

# Monitoring
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id

# Feature Flags
ENABLE_ANALYTICS=true
ENABLE_CACHING=true
```

## Containerization

### Docker Setup

**Dockerfile:**
```dockerfile
# Use Python 3.13 slim image
FROM python:3.13-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PORT=8000

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN adduser --disabled-password --gecos '' appuser \
    && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE $PORT

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:$PORT/health || exit 1

# Run the application
CMD ["sh", "-c", "gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT"]
```

**requirements.txt:**
```txt
getserving>=0.1.0
uvicorn[standard]>=0.34.0
gunicorn>=23.0.0
psycopg2-binary>=2.9.0
redis>=5.0.0
python-multipart>=0.0.20
jinja2>=3.1.0
pyyaml>=6.0.0
httpx>=0.28.0
```

**docker-compose.yml:**
```yaml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - ENVIRONMENT=production
      - DATABASE_URL=postgresql://postgres:password@db:5432/myapp
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis
    volumes:
      - ./logs:/app/logs
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  db:
    image: postgres:16
    environment:
      - POSTGRES_DB=myapp
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - app
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
```

### Multi-stage Docker Build

**Dockerfile.multistage:**
```dockerfile
# Build stage
FROM python:3.13-slim as builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install build dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Production stage
FROM python:3.13-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PATH=/home/appuser/.local/bin:$PATH \
    PORT=8000

# Install runtime dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN adduser --disabled-password --gecos '' appuser

# Copy Python dependencies from builder stage
COPY --from=builder /root/.local /home/appuser/.local

# Set work directory
WORKDIR /app

# Copy application code
COPY --chown=appuser:appuser . .

# Switch to non-root user
USER appuser

# Expose port
EXPOSE $PORT

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:$PORT/health || exit 1

# Run the application
CMD ["sh", "-c", "gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT"]
```

## Reverse Proxy Configuration

### Nginx Configuration

**nginx.conf:**
```nginx
events {
    worker_connections 1024;
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;

    # Logging
    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for"';

    access_log /var/log/nginx/access.log main;
    error_log /var/log/nginx/error.log;

    # Basic settings
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;
    client_max_body_size 100M;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types
        text/plain
        text/css
        text/xml
        text/javascript
        application/json
        application/javascript
        application/xml+rss
        application/atom+xml
        image/svg+xml;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req_zone $binary_remote_addr zone=login:10m rate=5r/m;

    # Upstream servers
    upstream app_servers {
        least_conn;
        server app:8000 max_fails=3 fail_timeout=30s;
        # Add more servers for load balancing
        # server app2:8000 max_fails=3 fail_timeout=30s;
        # server app3:8000 max_fails=3 fail_timeout=30s;
    }

    # HTTP to HTTPS redirect
    server {
        listen 80;
        server_name myapp.com www.myapp.com;
        return 301 https://$server_name$request_uri;
    }

    # HTTPS server
    server {
        listen 443 ssl http2;
        server_name myapp.com www.myapp.com;

        # SSL configuration
        ssl_certificate /etc/nginx/ssl/cert.pem;
        ssl_certificate_key /etc/nginx/ssl/key.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
        ssl_prefer_server_ciphers off;
        ssl_session_cache shared:SSL:10m;
        ssl_session_timeout 10m;

        # Security headers
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
        add_header X-Content-Type-Options nosniff always;
        add_header X-Frame-Options DENY always;
        add_header X-XSS-Protection "1; mode=block" always;
        add_header Referrer-Policy "strict-origin-when-cross-origin" always;

        # Static files
        location /static/ {
            alias /app/static/;
            expires 1y;
            add_header Cache-Control "public, immutable";
        }

        # API rate limiting
        location /api/ {
            limit_req zone=api burst=20 nodelay;
            proxy_pass http://app_servers;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header X-Forwarded-Host $host;
            proxy_set_header X-Forwarded-Port $server_port;
        }

        # Login rate limiting
        location /login {
            limit_req zone=login burst=5 nodelay;
            proxy_pass http://app_servers;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # Health check
        location /health {
            proxy_pass http://app_servers;
            access_log off;
        }

        # Main application
        location / {
            proxy_pass http://app_servers;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header X-Forwarded-Host $host;
            proxy_set_header X-Forwarded-Port $server_port;
            
            # WebSocket support
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            
            # Timeouts
            proxy_connect_timeout 60s;
            proxy_send_timeout 60s;
            proxy_read_timeout 60s;
        }
    }
}
```

### Apache Configuration

**apache.conf:**
```apache
<VirtualHost *:80>
    ServerName myapp.com
    ServerAlias www.myapp.com
    Redirect permanent / https://myapp.com/
</VirtualHost>

<VirtualHost *:443>
    ServerName myapp.com
    ServerAlias www.myapp.com

    # SSL Configuration
    SSLEngine on
    SSLCertificateFile /etc/ssl/certs/cert.pem
    SSLCertificateKeyFile /etc/ssl/private/key.pem
    SSLProtocol all -SSLv3 -TLSv1 -TLSv1.1
    SSLCipherSuite ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384

    # Security Headers
    Header always set Strict-Transport-Security "max-age=31536000; includeSubDomains"
    Header always set X-Content-Type-Options nosniff
    Header always set X-Frame-Options DENY
    Header always set X-XSS-Protection "1; mode=block"

    # Static files
    Alias /static /app/static
    <Directory "/app/static">
        Require all granted
        ExpiresActive On
        ExpiresDefault "access plus 1 year"
    </Directory>

    # Proxy to application
    ProxyPreserveHost On
    ProxyPass /static !
    ProxyPass / http://localhost:8000/
    ProxyPassReverse / http://localhost:8000/

    # Set headers for the backend
    ProxyPassReverse / http://localhost:8000/
    ProxyPreserveHost On
    RequestHeader set X-Forwarded-Proto "https"
    RequestHeader set X-Forwarded-Port "443"
</VirtualHost>
```

## Security Configuration

### SSL/TLS Setup

**Generate SSL certificates with Let's Encrypt:**
```bash
# Install Certbot
sudo apt-get install certbot python3-certbot-nginx

# Generate certificate
sudo certbot --nginx -d myapp.com -d www.myapp.com

# Auto-renewal
sudo crontab -e
# Add: 0 12 * * * /usr/bin/certbot renew --quiet
```

### Security Extension

**extensions/security/security_extension.py:**
```python
from serv.extensions import Extension
from serv.requests import Request
from serv.responses import ResponseBuilder
from bevy import dependency
from typing import AsyncIterator

class SecurityExtension(Extension):
    """Security extension for production deployments."""
    
    async def on_app_startup(self):
        """Initialize security settings."""
        config = self.__extension_spec__.config
        self.allowed_hosts = config.get("allowed_hosts", [])
        self.cors_origins = config.get("cors_origins", [])
        self.force_https = config.get("force_https", True)
    
    async def on_app_request_begin(self, router):
        """Add security middleware."""
        router.add_middleware(self.security_middleware)
    
    async def security_middleware(
        self,
        request: Request = dependency(),
        response: ResponseBuilder = dependency()
    ) -> AsyncIterator[None]:
        """Security middleware for production."""
        
        # Check allowed hosts
        host = request.headers.get("host", "")
        if self.allowed_hosts and host not in self.allowed_hosts:
            response.set_status(400)
            response.body("Invalid host")
            return
        
        # Force HTTPS in production
        if self.force_https and request.headers.get("x-forwarded-proto") != "https":
            if request.method == "GET":
                https_url = f"https://{host}{request.path}"
                if request.query_string:
                    https_url += f"?{request.query_string}"
                response.redirect(https_url, status_code=301)
                return
            else:
                response.set_status(400)
                response.body("HTTPS required")
                return
        
        # Add security headers
        response.add_header("X-Content-Type-Options", "nosniff")
        response.add_header("X-Frame-Options", "DENY")
        response.add_header("X-XSS-Protection", "1; mode=block")
        response.add_header("Referrer-Policy", "strict-origin-when-cross-origin")
        
        if self.force_https:
            response.add_header(
                "Strict-Transport-Security", 
                "max-age=31536000; includeSubDomains"
            )
        
        # CORS headers
        origin = request.headers.get("origin")
        if origin and origin in self.cors_origins:
            response.add_header("Access-Control-Allow-Origin", origin)
            response.add_header("Access-Control-Allow-Credentials", "true")
            response.add_header(
                "Access-Control-Allow-Methods", 
                "GET, POST, PUT, DELETE, OPTIONS"
            )
            response.add_header(
                "Access-Control-Allow-Headers",
                "Content-Type, Authorization, X-Requested-With"
            )
        
        yield
```

### Secrets Management

**extensions/secrets/secrets_extension.py:**
```python
import os
import json
from serv.extensions import Extension

class SecretsExtension(Extension):
    """Manage secrets from various sources."""
    
    async def on_app_startup(self):
        """Load secrets from environment or external services."""
        config = self.__extension_spec__.config
        
        # Load from environment variables
        self.secrets = {}
        for key in config.get("env_secrets", []):
            value = os.getenv(key)
            if value:
                self.secrets[key] = value
        
        # Load from file (for Docker secrets)
        secrets_file = config.get("secrets_file")
        if secrets_file and os.path.exists(secrets_file):
            with open(secrets_file) as f:
                file_secrets = json.load(f)
                self.secrets.update(file_secrets)
        
        # Load from external service (AWS Secrets Manager, etc.)
        await self._load_external_secrets(config)
        
        # Register secrets for dependency injection
        from serv.app import get_current_app
        app = get_current_app()
        app._container.instances[dict] = self.secrets
    
    async def _load_external_secrets(self, config):
        """Load secrets from external services."""
        # Example: AWS Secrets Manager
        aws_config = config.get("aws_secrets")
        if aws_config:
            try:
                import boto3
                client = boto3.client("secretsmanager")
                
                for secret_name in aws_config.get("secret_names", []):
                    response = client.get_secret_value(SecretId=secret_name)
                    secret_data = json.loads(response["SecretString"])
                    self.secrets.update(secret_data)
            except ImportError:
                print("boto3 not installed, skipping AWS secrets")
            except Exception as e:
                print(f"Error loading AWS secrets: {e}")
```

## Monitoring and Logging

### Health Check Extension

**extensions/monitoring/monitoring_extension.py:**
```python
import time
import psutil
from serv.extensions import Extension
from serv.routes import GetRequest
from serv.responses import ResponseBuilder
from bevy import dependency

class MonitoringExtension(Extension):
    """Monitoring and health check extension."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.start_time = time.time()
    
    async def on_app_request_begin(self, router):
        """Add monitoring routes."""
        config = self.__extension_spec__.config
        
        health_endpoint = config.get("health_endpoint", "/health")
        metrics_endpoint = config.get("metrics_endpoint", "/metrics")
        
        router.add_route(health_endpoint, self.health_check, methods=["GET"])
        router.add_route(metrics_endpoint, self.metrics, methods=["GET"])
    
    async def health_check(
        self,
        request: GetRequest,
        response: ResponseBuilder = dependency()
    ):
        """Health check endpoint."""
        
        # Basic health check
        health_data = {
            "status": "healthy",
            "timestamp": time.time(),
            "uptime": time.time() - self.start_time,
            "version": "1.0.0"
        }
        
        # Check database connection
        try:
            # Add your database health check here
            health_data["database"] = "healthy"
        except Exception as e:
            health_data["database"] = f"unhealthy: {str(e)}"
            health_data["status"] = "unhealthy"
            response.set_status(503)
        
        # Check Redis connection
        try:
            # Add your Redis health check here
            health_data["redis"] = "healthy"
        except Exception as e:
            health_data["redis"] = f"unhealthy: {str(e)}"
            health_data["status"] = "unhealthy"
            response.set_status(503)
        
        response.content_type("application/json")
        response.body(health_data)
    
    async def metrics(
        self,
        request: GetRequest,
        response: ResponseBuilder = dependency()
    ):
        """Metrics endpoint for monitoring."""
        
        # System metrics
        cpu_percent = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        metrics_data = {
            "system": {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_available": memory.available,
                "disk_percent": (disk.used / disk.total) * 100,
                "disk_free": disk.free
            },
            "application": {
                "uptime": time.time() - self.start_time,
                "timestamp": time.time()
            }
        }
        
        response.content_type("application/json")
        response.body(metrics_data)
```

### Structured Logging

**extensions/logging/logging_extension.py:**
```python
import logging
import json
import sys
from datetime import datetime
from serv.extensions import Extension

class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in ["name", "msg", "args", "levelname", "levelno", 
                          "pathname", "filename", "module", "lineno", 
                          "funcName", "created", "msecs", "relativeCreated", 
                          "thread", "threadName", "processName", "process",
                          "getMessage", "exc_info", "exc_text", "stack_info"]:
                log_entry[key] = value
        
        return json.dumps(log_entry)

class LoggingExtension(Extension):
    """Configure structured logging for production."""
    
    async def on_app_startup(self):
        """Configure logging."""
        config = self.__extension_spec__.config
        
        # Get configuration
        log_level = config.get("level", "INFO")
        log_format = config.get("format", "text")
        handlers = config.get("handlers", ["console"])
        
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, log_level))
        
        # Clear existing handlers
        root_logger.handlers.clear()
        
        # Add configured handlers
        for handler_name in handlers:
            if handler_name == "console":
                handler = logging.StreamHandler(sys.stdout)
            elif handler_name == "file":
                handler = logging.FileHandler("app.log")
            else:
                continue
            
            # Set formatter
            if log_format == "json":
                formatter = JSONFormatter()
            else:
                formatter = logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                )
            
            handler.setFormatter(formatter)
            root_logger.addHandler(handler)
        
        # Configure specific loggers
        logging.getLogger("uvicorn.access").setLevel(logging.INFO)
        logging.getLogger("uvicorn.error").setLevel(logging.INFO)
```

## Performance Optimization

### Caching Extension

**extensions/caching/caching_extension.py:**
```python
import redis
import json
import hashlib
from typing import Any, Optional
from serv.extensions import Extension
from serv.requests import Request
from serv.responses import ResponseBuilder
from bevy import dependency
from typing import AsyncIterator

class CachingExtension(Extension):
    """Redis-based caching extension."""
    
    async def on_app_startup(self):
        """Initialize Redis connection."""
        config = self.__extension_spec__.config
        redis_url = config.get("redis_url", "redis://localhost:6379/0")
        
        self.redis_client = redis.from_url(redis_url)
        self.default_ttl = config.get("default_ttl", 300)  # 5 minutes
        self.cache_prefix = config.get("cache_prefix", "serv_cache:")
        
        # Register for dependency injection
        from serv.app import get_current_app
        app = get_current_app()
        app._container.instances[redis.Redis] = self.redis_client
    
    async def on_app_shutdown(self):
        """Close Redis connection."""
        if hasattr(self, 'redis_client'):
            await self.redis_client.aclose()
    
    def cache_key(self, request: Request) -> str:
        """Generate cache key for request."""
        key_data = f"{request.method}:{request.path}:{request.query_string}"
        key_hash = hashlib.md5(key_data.encode()).hexdigest()
        return f"{self.cache_prefix}{key_hash}"
    
    async def get_cached_response(self, request: Request) -> Optional[dict]:
        """Get cached response for request."""
        cache_key = self.cache_key(request)
        
        try:
            cached_data = await self.redis_client.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
        except Exception as e:
            print(f"Cache get error: {e}")
        
        return None
    
    async def set_cached_response(
        self, 
        request: Request, 
        response_data: dict, 
        ttl: Optional[int] = None
    ):
        """Cache response for request."""
        cache_key = self.cache_key(request)
        ttl = ttl or self.default_ttl
        
        try:
            await self.redis_client.setex(
                cache_key, 
                ttl, 
                json.dumps(response_data)
            )
        except Exception as e:
            print(f"Cache set error: {e}")
    
    async def cache_middleware(
        self,
        request: Request = dependency(),
        response: ResponseBuilder = dependency()
    ) -> AsyncIterator[None]:
        """Caching middleware."""
        
        # Only cache GET requests
        if request.method != "GET":
            yield
            return
        
        # Check for cached response
        cached_response = await self.get_cached_response(request)
        if cached_response:
            response.set_status(cached_response["status"])
            for header, value in cached_response["headers"].items():
                response.add_header(header, value)
            response.body(cached_response["body"])
            return
        
        # Process request
        yield
        
        # Cache successful responses
        if 200 <= response._status < 300:
            response_data = {
                "status": response._status,
                "headers": dict(response._headers),
                "body": response._body_components[0] if response._body_components else ""
            }
            await self.set_cached_response(request, response_data)
```

### Database Connection Pooling

**extensions/database/database_extension.py:**
```python
import asyncpg
from typing import Optional
from serv.extensions import Extension

class DatabaseExtension(Extension):
    """Database connection pooling extension."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.pool: Optional[asyncpg.Pool] = None
    
    async def on_app_startup(self):
        """Initialize database connection pool."""
        config = self.__extension_spec__.config
        
        database_url = config.get("database_url")
        min_size = config.get("min_size", 5)
        max_size = config.get("max_size", 20)
        
        self.pool = await asyncpg.create_pool(
            database_url,
            min_size=min_size,
            max_size=max_size,
            command_timeout=60,
            server_settings={
                'jit': 'off'  # Disable JIT for better connection pool performance
            }
        )
        
        print(f"Database pool created: {min_size}-{max_size} connections")
        
        # Register pool for dependency injection
        from serv.app import get_current_app
        app = get_current_app()
        app._container.instances[asyncpg.Pool] = self.pool
    
    async def on_app_shutdown(self):
        """Close database connection pool."""
        if self.pool:
            await self.pool.close()
            print("Database pool closed")
```

## Cloud Deployment

### AWS Deployment

**deploy/aws/ecs-task-definition.json:**
```json
{
  "family": "serv-app",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "arn:aws:iam::ACCOUNT:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::ACCOUNT:role/ecsTaskRole",
  "containerDefinitions": [
    {
      "name": "serv-app",
      "image": "your-account.dkr.ecr.region.amazonaws.com/serv-app:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "ENVIRONMENT",
          "value": "production"
        }
      ],
      "secrets": [
        {
          "name": "DATABASE_URL",
          "valueFrom": "arn:aws:secretsmanager:region:account:secret:prod/database-url"
        },
        {
          "name": "SECRET_KEY",
          "valueFrom": "arn:aws:secretsmanager:region:account:secret:prod/secret-key"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/serv-app",
          "awslogs-region": "us-west-2",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 60
      }
    }
  ]
}
```

**deploy/aws/cloudformation.yaml:**
```yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: 'Serv Application Infrastructure'

Parameters:
  Environment:
    Type: String
    Default: production
    AllowedValues: [development, staging, production]
  
  ImageTag:
    Type: String
    Default: latest

Resources:
  # VPC and Networking
  VPC:
    Type: AWS::EC2::VPC
    Properties:
      CidrBlock: 10.0.0.0/16
      EnableDnsHostnames: true
      EnableDnsSupport: true
      Tags:
        - Key: Name
          Value: !Sub '${Environment}-serv-vpc'

  PublicSubnet1:
    Type: AWS::EC2::Subnet
    Properties:
      VpcId: !Ref VPC
      CidrBlock: 10.0.1.0/24
      AvailabilityZone: !Select [0, !GetAZs '']
      MapPublicIpOnLaunch: true

  PublicSubnet2:
    Type: AWS::EC2::Subnet
    Properties:
      VpcId: !Ref VPC
      CidrBlock: 10.0.2.0/24
      AvailabilityZone: !Select [1, !GetAZs '']
      MapPublicIpOnLaunch: true

  # ECS Cluster
  ECSCluster:
    Type: AWS::ECS::Cluster
    Properties:
      ClusterName: !Sub '${Environment}-serv-cluster'
      CapacityProviders:
        - FARGATE
        - FARGATE_SPOT

  # Application Load Balancer
  ALB:
    Type: AWS::ElasticLoadBalancingV2::LoadBalancer
    Properties:
      Name: !Sub '${Environment}-serv-alb'
      Scheme: internet-facing
      Type: application
      Subnets:
        - !Ref PublicSubnet1
        - !Ref PublicSubnet2
      SecurityGroups:
        - !Ref ALBSecurityGroup

  # ECS Service
  ECSService:
    Type: AWS::ECS::Service
    Properties:
      ServiceName: !Sub '${Environment}-serv-service'
      Cluster: !Ref ECSCluster
      TaskDefinition: !Ref ECSTaskDefinition
      DesiredCount: 2
      LaunchType: FARGATE
      NetworkConfiguration:
        AwsvpcConfiguration:
          SecurityGroups:
            - !Ref AppSecurityGroup
          Subnets:
            - !Ref PublicSubnet1
            - !Ref PublicSubnet2
          AssignPublicIp: ENABLED
      LoadBalancers:
        - ContainerName: serv-app
          ContainerPort: 8000
          TargetGroupArn: !Ref ALBTargetGroup

  # RDS Database
  DBSubnetGroup:
    Type: AWS::RDS::DBSubnetGroup
    Properties:
      DBSubnetGroupDescription: Subnet group for RDS database
      SubnetIds:
        - !Ref PublicSubnet1
        - !Ref PublicSubnet2

  Database:
    Type: AWS::RDS::DBInstance
    Properties:
      DBInstanceIdentifier: !Sub '${Environment}-serv-db'
      DBInstanceClass: db.t3.micro
      Engine: postgres
      EngineVersion: '16.1'
      AllocatedStorage: 20
      StorageType: gp2
      DBName: servapp
      MasterUsername: postgres
      MasterUserPassword: !Ref DatabasePassword
      DBSubnetGroupName: !Ref DBSubnetGroup
      VPCSecurityGroups:
        - !Ref DatabaseSecurityGroup

Outputs:
  LoadBalancerDNS:
    Description: DNS name of the load balancer
    Value: !GetAtt ALB.DNSName
    Export:
      Name: !Sub '${Environment}-serv-alb-dns'
```

### Kubernetes Deployment

**k8s/deployment.yaml:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: serv-app
  labels:
    app: serv-app
spec:
  replicas: 3
  selector:
    matchLabels:
      app: serv-app
  template:
    metadata:
      labels:
        app: serv-app
    spec:
      containers:
      - name: serv-app
        image: your-registry/serv-app:latest
        ports:
        - containerPort: 8000
        env:
        - name: ENVIRONMENT
          value: "production"
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: serv-secrets
              key: database-url
        - name: SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: serv-secrets
              key: secret-key
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: serv-app-service
spec:
  selector:
    app: serv-app
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: ClusterIP
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: serv-app-ingress
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/rate-limit: "100"
spec:
  tls:
  - hosts:
    - myapp.com
    secretName: serv-app-tls
  rules:
  - host: myapp.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: serv-app-service
            port:
              number: 80
```

## Deployment Scripts

### Automated Deployment Script

**deploy.sh:**
```bash
#!/bin/bash

set -e

# Configuration
ENVIRONMENT=${1:-production}
IMAGE_TAG=${2:-latest}
REGISTRY="your-registry.com"
APP_NAME="serv-app"

echo "🚀 Deploying $APP_NAME to $ENVIRONMENT environment"

# Build and push Docker image
echo "📦 Building Docker image..."
docker build -t $REGISTRY/$APP_NAME:$IMAGE_TAG .

echo "📤 Pushing Docker image..."
docker push $REGISTRY/$APP_NAME:$IMAGE_TAG

# Deploy based on environment
case $ENVIRONMENT in
  "production")
    echo "🌐 Deploying to production..."
    # Update ECS service
    aws ecs update-service \
      --cluster production-serv-cluster \
      --service production-serv-service \
      --force-new-deployment
    ;;
  
  "staging")
    echo "🧪 Deploying to staging..."
    # Update staging environment
    kubectl set image deployment/serv-app-staging \
      serv-app=$REGISTRY/$APP_NAME:$IMAGE_TAG
    ;;
  
  "development")
    echo "🔧 Deploying to development..."
    docker-compose -f docker-compose.dev.yml up -d
    ;;
  
  *)
    echo "❌ Unknown environment: $ENVIRONMENT"
    exit 1
    ;;
esac

echo "✅ Deployment completed successfully!"

# Health check
echo "🏥 Performing health check..."
sleep 30

case $ENVIRONMENT in
  "production")
    HEALTH_URL="https://myapp.com/health"
    ;;
  "staging")
    HEALTH_URL="https://staging.myapp.com/health"
    ;;
  "development")
    HEALTH_URL="http://localhost:8000/health"
    ;;
esac

if curl -f $HEALTH_URL > /dev/null 2>&1; then
  echo "✅ Health check passed!"
else
  echo "❌ Health check failed!"
  exit 1
fi
```

### CI/CD Pipeline (GitHub Actions)

**.github/workflows/deploy.yml:**
```yaml
name: Deploy Serv Application

on:
  push:
    branches: [main, staging, develop]
  pull_request:
    branches: [main]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.13'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pytest pytest-asyncio
    
    - name: Run tests
      run: pytest
    
    - name: Run linting
      run: |
        pip install ruff
        ruff check .

  build:
    needs: test
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    
    steps:
    - name: Checkout repository
      uses: actions/checkout@v4
    
    - name: Log in to Container Registry
      uses: docker/login-action@v3
      with:
        registry: ${{ env.REGISTRY }}
        username: ${{ github.actor }}
        password: ${{ secrets.GITHUB_TOKEN }}
    
    - name: Extract metadata
      id: meta
      uses: docker/metadata-action@v5
      with:
        images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
        tags: |
          type=ref,event=branch
          type=ref,event=pr
          type=sha
    
    - name: Build and push Docker image
      uses: docker/build-push-action@v5
      with:
        context: .
        push: true
        tags: ${{ steps.meta.outputs.tags }}
        labels: ${{ steps.meta.outputs.labels }}

  deploy-staging:
    if: github.ref == 'refs/heads/staging'
    needs: build
    runs-on: ubuntu-latest
    environment: staging
    
    steps:
    - name: Deploy to staging
      run: |
        echo "Deploying to staging environment"
        # Add your staging deployment commands here

  deploy-production:
    if: github.ref == 'refs/heads/main'
    needs: build
    runs-on: ubuntu-latest
    environment: production
    
    steps:
    - name: Deploy to production
      run: |
        echo "Deploying to production environment"
        # Add your production deployment commands here
```

## Best Practices

### 1. Environment Separation

```python
# Good: Separate configurations for each environment
config/
├── development.yaml
├── staging.yaml
├── production.yaml
└── testing.yaml

# Avoid: Single configuration file with environment variables
```

### 2. Security Hardening

```python
# Good: Security-focused configuration
- Use HTTPS in production
- Set secure headers
- Validate all inputs
- Use secrets management
- Regular security updates

# Avoid: Development settings in production
```

### 3. Monitoring and Alerting

```python
# Good: Comprehensive monitoring
- Health checks
- Application metrics
- Error tracking
- Performance monitoring
- Log aggregation

# Avoid: No monitoring or basic monitoring only
```

### 4. Graceful Shutdown

```python
# Good: Handle shutdown gracefully
async def graceful_shutdown():
    # Close database connections
    # Finish processing requests
    # Clean up resources
    pass

# Avoid: Abrupt termination
```

### 5. Resource Management

```python
# Good: Proper resource limits
resources:
  requests:
    memory: "256Mi"
    cpu: "250m"
  limits:
    memory: "512Mi"
    cpu: "500m"

# Avoid: No resource limits
```

## Troubleshooting

### Common Issues

1. **Application won't start**
   - Check configuration files
   - Verify environment variables
   - Check database connectivity
   - Review logs for errors

2. **High memory usage**
   - Check for memory leaks
   - Review database connection pooling
   - Monitor garbage collection
   - Optimize caching

3. **Slow response times**
   - Add database indexes
   - Implement caching
   - Optimize queries
   - Use connection pooling

4. **SSL/TLS issues**
   - Verify certificate validity
   - Check certificate chain
   - Ensure proper configuration
   - Test with SSL tools

### Debugging Commands

```bash
# Check application logs
docker logs serv-app

# Check resource usage
docker stats serv-app

# Test health endpoint
curl -f http://localhost:8000/health

# Check database connectivity
psql $DATABASE_URL -c "SELECT 1"

# Monitor application metrics
curl http://localhost:8000/metrics
```

## Next Steps

- **[Performance](performance.md)** - Optimize application performance
- **[Monitoring](monitoring.md)** - Advanced monitoring and alerting
- **[Security](security.md)** - Advanced security practices 