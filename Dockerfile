FROM python:3.12-slim-bookworm

WORKDIR /app

# Create a non-root user for runtime security
RUN groupadd -r northwind && useradd -r -g northwind app

# Install only the application code and dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY run.py .

RUN chown -R app:northwind /app
USER app

EXPOSE 8000

ENV PORT=8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["python", "-m", "app"]
