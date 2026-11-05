"""Modelos de IA: separação de faixas, transcrição de notas e letra.

Cada modelo é importado só quando usado. Assim, análise, cifra e tablatura
funcionam mesmo sem PyTorch instalado.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from .models import Nota, Palavra

MODELO_SEPARACAO = "htdemucs_6s"  # separa voz, bateria, baixo, guitarra, piano e outros

# Nome do arquivo do Demucs -> nome no Prismo
FAIXAS = {
    "vocals": "voz",
    "guitar": "guitarra",
    "bass": "baixo",
    "drums": "bateria",
    "piano": "piano",
    "other": "outros",
}

EXTENSOES_VIDEO = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".3gp"}


class DependenciaAusente(RuntimeError):
    pass


def extrair_audio(caminho: str, pasta: Path) -> Path:
    """Vídeo vira WAV (precisa do ffmpeg). Áudio passa direto."""
    origem = Path(caminho)
    if origem.suffix.lower() not in EXTENSOES_VIDEO:
        return origem
    if not shutil.which("ffmpeg"):
        raise DependenciaAusente("Para enviar vídeo, instale o ffmpeg (https://ffmpeg.org/download.html).")
    destino = pasta / (origem.stem + ".wav")
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(origem), "-vn", "-ac", "2", "-ar", "44100", str(destino)],
        check=True,
    )
    return destino


def separar_faixas(caminho: str, pasta_saida: Path, dispositivo: str | None = None) -> dict[str, Path]:
    """Separa o áudio em faixas com o Demucs. Retorna {nome_da_faixa: arquivo}."""
    try:
        import demucs  # noqa: F401
    except ImportError as erro:
        raise DependenciaAusente("Instale a separação com: pip install -e \".[separacao]\"") from erro

    cmd = [sys.executable, "-m", "demucs", "-n", MODELO_SEPARACAO, "-o", str(pasta_saida), str(caminho)]
    if dispositivo:
        cmd += ["-d", dispositivo]
    subprocess.run(cmd, check=True)

    pasta = pasta_saida / MODELO_SEPARACAO / Path(caminho).stem
    faixas = {}
    for arquivo, nome in FAIXAS.items():
        origem = pasta / f"{arquivo}.wav"
        if origem.exists():
            destino = pasta_saida / f"{nome}.wav"
            shutil.move(str(origem), destino)
            faixas[nome] = destino
    shutil.rmtree(pasta_saida / MODELO_SEPARACAO, ignore_errors=True)
    return faixas


def transcrever_notas(caminho: str, instrumento: str = "guitarra") -> list[Nota]:
    """Áudio (de preferência uma faixa isolada) -> notas, com o Basic Pitch."""
    try:
        from basic_pitch import ICASSP_2022_MODEL_PATH
        from basic_pitch.inference import predict
    except ImportError as erro:
        raise DependenciaAusente("Instale a transcrição com: pip install -e \".[transcricao]\"") from erro

    # A versão ONNX do modelo roda na CPU e não disputa a GPU com a separação de faixas
    modelo = Path(ICASSP_2022_MODEL_PATH).parent / "nmp.onnx"
    if not modelo.exists():
        modelo = Path(ICASSP_2022_MODEL_PATH)

    # Faixas de frequência por instrumento reduzem notas fantasmas
    limites = {
        "guitarra": (75.0, 1400.0),
        "violao": (75.0, 1400.0),
        "baixo": (35.0, 400.0),
        "voz": (80.0, 1100.0),
        "piano": (27.0, 4200.0),
    }
    minimo, maximo = limites.get(instrumento, (30.0, 4000.0))
    _, _, eventos = predict(
        str(caminho),
        modelo,
        onset_threshold=0.5,
        frame_threshold=0.3,
        minimum_note_length=80,
        minimum_frequency=minimo,
        maximum_frequency=maximo,
        multiple_pitch_bends=False,
    )
    notas = [Nota(float(ini), float(fim), int(midi), float(amp)) for ini, fim, midi, amp, *_ in eventos]
    return remover_harmonicos(sorted(notas, key=lambda n: (n.inicio, n.midi)))


# Harmônicos naturais acima da fundamental (em semitons): oitava, 12ª, 2 oitavas, 17ª, 19ª
_HARMONICOS = (12, 19, 24, 28, 31)


def remover_harmonicos(notas: list[Nota], janela: float = 0.06) -> list[Nota]:
    """Remove "notas fantasmas": harmônicos de uma nota mais grave e mais forte.

    O modelo às vezes ouve o harmônico de uma corda como se fosse outra nota
    tocada. Se, quando uma nota começa, outra mais forte já está soando
    exatamente num intervalo de harmônico abaixo dela, ela é descartada.
    """
    mantidas = []
    for n in notas:
        fantasma = any(
            o.inicio - janela <= n.inicio < o.fim
            and (n.midi - o.midi) in _HARMONICOS
            and o.intensidade >= n.intensidade * 0.9
            and (n.midi - o.midi) != 12  # oitavas são tocadas de verdade com frequência
            for o in notas
            if o is not n
        )
        if not fantasma:
            mantidas.append(n)
    return mantidas


def transcrever_letra(caminho_voz: str, idioma: str | None = None, modelo: str = "small") -> tuple[list[Palavra], str | None]:
    """Voz isolada -> (palavras com tempo, idioma detectado), com o Whisper (faster-whisper).

    Sem `idioma`, o Whisper detecta o idioma da música e transcreve nele, sem traduzir.
    Forçar um idioma diferente do cantado faz o modelo "traduzir" e inventar frases.
    """
    try:
        from faster_whisper import WhisperModel
    except ImportError as erro:
        raise DependenciaAusente("Instale a letra com: pip install -e \".[letra]\"") from erro

    def reconhecer(device: str, compute_type: str) -> tuple[list[Palavra], str | None]:
        whisper = WhisperModel(modelo, device=device, compute_type=compute_type)
        segmentos, info = whisper.transcribe(
            str(caminho_voz), language=idioma, task="transcribe", word_timestamps=True, vad_filter=True
        )
        palavras = []
        for seg in segmentos:
            for w in seg.words or []:
                texto = w.word.strip()
                if texto:
                    palavras.append(Palavra(float(w.start), float(w.end), texto))
        return palavras, getattr(info, "language", None) or idioma

    try:
        return reconhecer("auto", "auto")
    except (RuntimeError, OSError, ValueError):
        # Bibliotecas de GPU ausentes ou incompatíveis: a letra sai na CPU, um pouco mais devagar
        return reconhecer("cpu", "int8")
