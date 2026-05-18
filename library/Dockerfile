# Django API + SQLite index (build context = this `library/` directory).
# Copy `db_index.sqlite3` into `library/` before `docker build`, or mount it at runtime at /app/db_index.sqlite3
FROM python:3.12-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY . .

EXPOSE 8000

# Railway / Render / Fly set PORT; default 8000 for local docker run.
CMD ["sh", "-c", "python manage.py migrate --noinput && exec gunicorn library.wsgi:application --bind 0.0.0.0:${PORT:-8000}"]
