FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Run as a normal user; /data holds the SQLite file when no DATABASE_URL points at Postgres
RUN useradd --create-home appuser && mkdir /data && chown appuser /data
USER appuser
ENV DATABASE_URL=sqlite:////data/sessio.db

# Hosts such as Render tell the app which port to use through PORT; locally it stays 8000
ENV PORT=8000
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --retries=5 \
  CMD python -c "import os, urllib.request as u; u.urlopen('http://localhost:%s/api/health' % os.environ.get('PORT', '8000'))"
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
