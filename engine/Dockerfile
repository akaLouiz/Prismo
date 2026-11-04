# Imagem do motor do Prismo para servidores com GPU NVIDIA (RunPod, Modal, AWS, GCP...)
# Construir:  docker build -t prismo-engine .
# Rodar:      docker run --gpus all -p 8000:8000 --env-file .env prismo-engine
FROM pytorch/pytorch:2.4.1-cuda12.1-cudnn9-runtime

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    TF_CPP_MIN_LOG_LEVEL=3 \
    PRISMO_DISPOSITIVO=cuda \
    PRISMO_PASTA=/tmp/prismo \
    PORT=8000

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libsndfile1 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md ./
COPY prismo_engine ./prismo_engine
RUN pip install --no-cache-dir -e ".[completo]"

# Baixa os modelos durante a construção, para a primeira música não esperar o download
RUN python -c "from demucs.pretrained import get_model; get_model('htdemucs_6s')" \
 && python -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8')"

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/saude')"
CMD ["prismo-api"]
