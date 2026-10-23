FROM python:3.13-slim
WORKDIR /app
COPY pyproject.toml ./
COPY envpilot ./envpilot
RUN pip install --no-cache-dir .
CMD ["uvicorn", "envpilot.api:app", "--host", "0.0.0.0", "--port", "8000"]
