# Multi-stage build for smaller final image

# ---- Stage 1: builder (compile wheels) ----
FROM python:3.11-slim AS builder

WORKDIR /build

# psycopg2-binary needs build essentials? — actually binary distribution doesn't,
# but having gcc available helps for other native deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt


# ---- Stage 2: runtime (lean) ----
FROM python:3.11-slim AS runtime

# Create non-root user (security best practice)
RUN useradd -m -u 1000 nbpuser

WORKDIR /app

# Copy wheels from builder stage
COPY --from=builder /root/.local /home/nbpuser/.local

# Copy application code
COPY src/ ./src/
COPY sql/ ./sql/
COPY scripts/ ./scripts/

# Set ownership and switch to non-root
RUN chown -R nbpuser:nbpuser /app /home/nbpuser/.local
USER nbpuser

# Add user-local Python packages to PATH
ENV PATH="/home/nbpuser/.local/bin:${PATH}"
ENV PYTHONPATH="/app"
ENV PYTHONUNBUFFERED=1

# Default command (overridden in docker-compose for different services)
CMD ["python", "-m", "src.main"]