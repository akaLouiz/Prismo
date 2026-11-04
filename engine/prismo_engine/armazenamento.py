"""Envio dos arquivos gerados para o Storage do Supabase."""

from __future__ import annotations

import mimetypes
import shutil
import subprocess
from pathlib import Path

import httpx

TIPOS = {
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".musicxml": "application/vnd.recordare.musicxml+xml",
    ".mid": "audio/midi",
    ".txt": "text/plain; charset=utf-8",
    ".json": "application/json",
}


class ErroArmazenamento(RuntimeError):
    pass


def comprimir_para_mp3(wav: Path, kbps: int = 192) -> Path:
    """Converte a faixa para MP3 (bem menor para o navegador). Sem ffmpeg, mantém o WAV."""
    if not shutil.which("ffmpeg"):
        return wav
    mp3 = wav.with_suffix(".mp3")
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-codec:a", "libmp3lame", "-b:a", f"{kbps}k", str(mp3)],
        check=True,
    )
    return mp3


class Supabase:
    """Cliente mínimo do Storage do Supabase (só o que o motor precisa)."""

    def __init__(self, url: str, chave_servico: str, timeout: float = 120.0):
        self.url = url.rstrip("/")
        self._cabecalhos = {"Authorization": f"Bearer {chave_servico}", "apikey": chave_servico}
        self._timeout = timeout

    def enviar(self, bucket: str, caminho: str, arquivo: Path) -> str:
        tipo = TIPOS.get(arquivo.suffix.lower()) or mimetypes.guess_type(arquivo.name)[0] or "application/octet-stream"
        destino = f"{self.url}/storage/v1/object/{bucket}/{caminho}"
        with arquivo.open("rb") as f:
            resposta = httpx.post(
                destino,
                content=f.read(),
                headers={**self._cabecalhos, "Content-Type": tipo, "x-upsert": "true"},
                timeout=self._timeout,
            )
        if resposta.status_code >= 300:
            raise ErroArmazenamento(f"Falha ao enviar {caminho} para o bucket {bucket}: {resposta.status_code} {resposta.text[:200]}")
        return caminho
