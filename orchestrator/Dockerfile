FROM python:3.12-slim
WORKDIR /app

RUN pip install --no-cache-dir \
    fastapi==0.115.0 \
    "uvicorn[standard]==0.30.6" \
    pydantic==2.8.2 \
    redis==5.0.8 \
    psycopg2-binary==2.9.9

COPY schemas/ ./schemas/
COPY orchestrator/app.py ./app.py

ENV PYTHONPATH=/app

EXPOSE 8080
CMD ["python", "app.py"]
