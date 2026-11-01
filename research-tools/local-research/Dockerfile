FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8 CRAWL4AI_NO_CLOUD_NOTICE=1 \
    LOCAL_RESEARCH_STATE=/data/reader LOCAL_RESEARCH_TESSDATA=/app/tessdata \
    SEARXNG_URL=http://host.docker.internal:8088
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock ./
# CPU/browser edition: no PyTorch or Docling model weights in the default image.
RUN uv sync --frozen --extra browser --no-dev --no-install-project && \
    .venv/bin/python -m playwright install --with-deps chromium && \
    mkdir -p /app/tessdata && \
    .venv/bin/python -c "import urllib.request; [urllib.request.urlretrieve('https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/main/'+lang+'.traineddata', '/app/tessdata/'+lang+'.traineddata') for lang in ['eng','tha']]" && \
    uv cache clean && rm -rf /var/lib/apt/lists/*
COPY src ./src
COPY server.py ./server.py
RUN uv sync --frozen --extra browser --no-dev
VOLUME /data
ENTRYPOINT ["/app/.venv/bin/python", "/app/server.py"]
