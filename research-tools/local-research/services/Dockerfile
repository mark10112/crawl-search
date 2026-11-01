FROM pytorch/pytorch:2.7.1-cuda12.6-cudnn9-runtime
ENV PYTHONUNBUFFERED=1 HF_HUB_DISABLE_XET=1 TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=4
RUN pip install --no-cache-dir transformers==5.22.1 accelerate pillow rapidocr==3.10.0 onnxruntime python-bidi
WORKDIR /service
COPY ocr_service.py /service/ocr_service.py
ENTRYPOINT ["python", "/service/ocr_service.py"]
