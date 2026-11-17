# ---- Build Stage ----
FROM python:3.11-slim-bookworm AS builder

# Install build tools if any wheels need compiling
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Create virtual environment and upgrade packaging tools to patched versions
COPY backend/requirements.txt .
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir --upgrade "pip>=26.2.0" "setuptools>=84.1.0" "wheel>=0.46.2" && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# ---- Runtime Stage ----
FROM python:3.11-slim-bookworm

# Apply OS security patches and install only curl for healthcheck
# (default-libmysqlclient-dev / mariadb-common is omitted since PyMySQL is pure Python)
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Remove ensurepip bundled wheels (contains vulnerable setuptools 70.3.0 whl)
# and all legacy packaging tools from the base Debian/Python OS.
# The application runs strictly inside /opt/venv which has clean, fully patched dependencies.
RUN rm -rf /usr/local/lib/python3.11/ensurepip \
           /usr/local/lib/python3.11/site-packages/* \
           /usr/local/lib/python3.11/dist-packages/* \
           /usr/lib/python3/dist-packages/setuptools* \
           /usr/share/python-wheels/* \
           /usr/local/bin/pip* \
           /usr/local/bin/wheel* \
           /root/.cache /root/.local && \
    find /usr -name "*setuptools*70.3*" -exec rm -rf {} + 2>/dev/null || true

# Create dedicated non-root application user
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid 1000 --no-create-home --shell /usr/sbin/nologin appuser

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application code
COPY backend/ ./backend/

# Set ownership
RUN chown -R appuser:appuser /app

# Set working directory to backend where app.py, config.py, and templates live
WORKDIR /app/backend

# Switch to non-root user
USER appuser

# Environment variables
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/app/backend:$PYTHONPATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 5000

# Container healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl --fail http://localhost:5000/health || exit 1

# Start Gunicorn server
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "3", "--timeout", "120", "app:app"]
