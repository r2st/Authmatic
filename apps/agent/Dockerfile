# Agent service image (ticket 0020). Python slim, non-root, pinned deps.
FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps for pdfplumber / asyncpg wheels are present in slim; add build
# tools only if a wheel is missing for the target arch.
COPY apps/agent/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY apps/agent ./apps/agent
COPY fixtures ./fixtures
COPY assets ./assets

RUN useradd --system --uid 1001 agent && chown -R agent:agent /app
USER agent

WORKDIR /app/apps/agent
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/healthz').status==200 else 1)"
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
