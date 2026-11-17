# ---- Build Stage ----
FROM python:3.11-slim-bookworm AS builder

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        pkg-config \
        default-libmysqlclient-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Install Python dependencies into a virtual environment
COPY backend/requirements.txt .
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir --upgrade pip setuptools wheel && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# ---- Runtime Stage ----
FROM python:3.11-slim-bookworm

# Apply all OS security patches
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
        default-libmysqlclient-dev \
        curl && \
    rm -rf /var/lib/apt/lists/*

# Create a non-root user
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid 1000 --no-create-home --shell /usr/sbin/nologin appuser

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application code
COPY backend/ ./backend/

# Set ownership
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Add venv to PATH
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl --fail http://localhost:5000/health || exit 1

# Run with Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "3", "--timeout", "120", "backend.app:app"]
