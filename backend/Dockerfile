FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install uv
CMD ["uv", "run", "uvicorn", "backend.src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]