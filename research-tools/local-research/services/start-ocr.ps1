$ErrorActionPreference='Stop'
docker run -d --name local-research-ocr --restart unless-stopped --gpus all --shm-size 1g `
    -p 127.0.0.1:8091:8091 `
    --mount "type=bind,source=$PSScriptRoot,target=/service,readonly" `
    --mount 'type=volume,source=ocr-benchmark-models,target=/cache' `
    -e 'HF_HOME=/cache/hf' -e 'HF_HUB_DISABLE_XET=1' `
    --entrypoint python ocr-multilingual-bench:2026-11-01 /service/ocr_service.py
