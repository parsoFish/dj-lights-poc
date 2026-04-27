FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir -e ".[dev]"

COPY dj_lights ./dj_lights
COPY data ./data

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["uvicorn", "dj_lights.server.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
