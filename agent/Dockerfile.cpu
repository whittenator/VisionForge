FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src:/agent/src

WORKDIR /app

# Install backend deps (Celery tasks + ML libs are imported by the worker).
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /app/requirements.txt

# Backend source supplies the Celery app + task modules executed by the worker.
COPY backend /app

# Install agent-only deps and copy agent source.
COPY agent/requirements.txt /agent/requirements.txt
RUN pip install --no-cache-dir -r /agent/requirements.txt
COPY agent /agent

# Agent state (identity.json) persists here; mount a volume in production.
RUN mkdir -p /var/lib/vf-agent && chmod 700 /var/lib/vf-agent

EXPOSE 9443

ENTRYPOINT ["python", "-m", "vf_agent.main"]
