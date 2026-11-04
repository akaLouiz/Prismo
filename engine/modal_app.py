"""Motor do Prismo no Modal (https://modal.com).

Duas peças:
- `api`: o endereço que o site chama (POST /processar, GET /status, GET /saude). Roda numa
  máquina pequena, sem GPU, e responde na hora.
- `processar_musica`: processa uma música numa GPU L4, que liga quando chega uma música e
  desliga sozinha depois. Paga-se só pelos segundos de uso.

Publicar:  modal deploy modal_app.py   (a automação do GitHub faz isso a cada atualização)
Segredos:  um Secret chamado "prismo-engine" no painel do Modal, com PRISMO_TOKEN,
           PRISMO_CALLBACK_TOKEN, SUPABASE_URL e PRISMO_HOSTS_CALLBACK (veja docs/modal.md).
"""

import modal

NOME = "prismo-engine"

imagem = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg", "libsndfile1")
    .uv_pip_install(
        "torch==2.4.1",
        "torchaudio==2.4.1",
        "demucs==4.0.1",
        "basic-pitch[onnx]==0.4.0",
        "numpy<2",
        "faster-whisper>=1.0,<2",
        "librosa>=0.10",
        "soundfile>=0.12",
        "scipy>=1.10",
        "music21>=9.1",
        "fastapi>=0.110",
        "httpx>=0.27",
    )
    .env({"TF_CPP_MIN_LOG_LEVEL": "3", "PRISMO_DISPOSITIVO": "cuda", "PRISMO_PASTA": "/tmp/prismo"})
    # Baixa os modelos durante a construção da imagem: a primeira música não espera o download
    .run_commands(
        "python -c \"from demucs.pretrained import get_model; get_model('htdemucs_6s')\"",
        "python -c \"from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8')\"",
    )
    .add_local_python_source("prismo_engine")
)

app = modal.App(NOME, image=imagem)
segredos = [modal.Secret.from_name(NOME)]
# Estado de cada música (fila, etapa, erro), compartilhado entre a API e as GPUs
estado = modal.Dict.from_name(f"{NOME}-estado", create_if_missing=True)


@app.function(gpu="L4", timeout=20 * 60, secrets=segredos, max_containers=5, scaledown_window=60)
def processar_musica(pedido: dict) -> dict:
    from prismo_engine.api import Config
    from prismo_engine.fila_remota import ExecutorRemoto

    return ExecutorRemoto(Config.do_ambiente(), estado).executar(pedido)


@app.function(secrets=segredos, cpu=1.0, memory=1024, scaledown_window=5 * 60)
@modal.concurrent(max_inputs=50)
@modal.asgi_app()
def api():
    from prismo_engine.api import Config, criar_app
    from prismo_engine.fila_remota import FilaRemota

    config = Config.do_ambiente()
    fila = FilaRemota(config, estado, lambda pedido: processar_musica.spawn(pedido))
    return criar_app(config, fila)
