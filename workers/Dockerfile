FROM python:3.12-slim
WORKDIR /app

RUN pip install --no-cache-dir \
    pydantic==2.8.2 \
    redis==5.0.8 \
    psycopg2-binary==2.9.9 \
    anthropic==0.40.0
# anthropic 0.40.x bundles httpx — no extra network deps required.
# To add OpenAI support: append 'openai>=1.0' above.

# Non-root uid 1000 prevents root-owned files in shared/
# If shared/ is currently root-owned on the VPS, run once before building:
#   sudo chown -R 1000:1000 /home/administrator/ai-worker-team/shared
RUN useradd --uid 1000 --no-create-home --shell /bin/false worker

COPY schemas/    ./schemas/
COPY providers/  ./providers/
COPY workers/app.py ./app.py

ENV PYTHONPATH=/app
USER worker
CMD ["python", "app.py"]
