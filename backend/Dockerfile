FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY pyproject.toml requirements.lock ./
COPY app ./app
RUN pip install --no-cache-dir --constraint requirements.lock . \
    && groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home app \
    && mkdir /app/data \
    && chown app:app /app/data

COPY alembic.ini ./
COPY migrations ./migrations

USER app
EXPOSE 6931

CMD ["sh", "-c", "python -m alembic upgrade head && exec python -m uvicorn app.main:app --host 0.0.0.0 --port 6931"]
