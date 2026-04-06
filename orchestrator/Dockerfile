FROM python:3.12-slim
WORKDIR /app

RUN pip install --no-cache-dir \
    fastapi==0.115.0 \
    "uvicorn[standard]==0.30.6" \
    pydantic==2.8.2 \
    redis==5.0.8 \
    psycopg2-binary==2.9.9 \
    jinja2==3.1.4 \
    aiofiles==23.2.1 \
    python-multipart

COPY schemas/ ./schemas/
COPY orchestrator/app.py ./app.py

# A9: Jinja2 templates and static assets for the dashboard UI
COPY orchestrator/templates/ ./templates/
COPY orchestrator/static/    ./static/

ENV PYTHONPATH=/app

EXPOSE 8080
CMD ["python", "app.py"]
