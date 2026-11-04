"""API HTTP do motor: o site (Lovable/Supabase) pede o processamento e recebe o resultado.

Fluxo:
1. O site chama POST /processar com o endereço do áudio e o callback.
2. A API responde na hora (202) e coloca a música na fila.
3. Durante o processamento, a API avisa cada etapa no callback (tipo "progresso").
4. No fim, envia as faixas e os arquivos ao Storage do Supabase e chama o
   callback com o resultado completo (tipo "concluido") ou com o erro ("erro").

Configuração por variáveis de ambiente (veja docs/contrato-api.md):
    PRISMO_TOKEN               obrigatório: senha que o site usa para chamar a API
    PRISMO_CALLBACK_TOKEN      senha enviada no callback (padrão: a mesma do PRISMO_TOKEN)
    SUPABASE_URL               ex.: https://xyzcompany.supabase.co
    SUPABASE_SERVICE_ROLE_KEY  chave de serviço, para enviar arquivos ao Storage
    PRISMO_BUCKET_FAIXAS       padrão: stems
    PRISMO_BUCKET_RESULTADOS   padrão: results
    PRISMO_HOSTS_PERMITIDOS    hosts aceitos em audio_url, separados por vírgula
                               (padrão: o host do SUPABASE_URL)
    PRISMO_HOSTS_CALLBACK      hosts aceitos em callback_url, separados por vírgula
                               (padrão: os mesmos de PRISMO_HOSTS_PERMITIDOS); inclua o domínio do site
    PRISMO_MAX_MB              tamanho máximo do arquivo (padrão: 60)
    PRISMO_TRABALHADORES       músicas processadas ao mesmo tempo (padrão: 1, uma GPU)
    PRISMO_DISPOSITIVO         "cuda" ou "cpu" (padrão: automático)
    PRISMO_PASTA               pasta de trabalho temporária (padrão: /tmp/prismo)
"""

from __future__ import annotations

import hmac
import logging
import os
import queue
import shutil
import threading
import time
import traceback
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field

from . import __version__
from .armazenamento import Supabase, caminho_do_link, comprimir_para_mp3, enviar_por_link
from .pipeline import ETAPAS, processar

log = logging.getLogger("prismo.api")
logging.basicConfig(level=logging.INFO, format="[prismo] %(asctime)s %(levelname)s %(message)s")

EXTENSOES_ACEITAS = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac", ".mp4", ".mov", ".webm", ".mkv", ".m4v", ".3gp"}
TIPO_PARA_EXTENSAO = {
    "audio/mpeg": ".mp3", "audio/mp3": ".mp3", "audio/wav": ".wav", "audio/x-wav": ".wav", "audio/wave": ".wav",
    "audio/mp4": ".m4a", "audio/x-m4a": ".m4a", "audio/aac": ".aac", "audio/ogg": ".ogg", "audio/flac": ".flac",
    "video/mp4": ".mp4", "video/quicktime": ".mov", "video/webm": ".webm", "audio/webm": ".webm",
}


# ---------------------------------------------------------------- configuração

@dataclass
class Config:
    token: str
    token_callback: str
    supabase_url: str | None
    supabase_chave: str | None
    bucket_faixas: str
    bucket_resultados: str
    hosts_permitidos: set[str]
    hosts_callback: set[str]
    max_bytes: int
    trabalhadores: int
    dispositivo: str | None
    pasta: Path

    @classmethod
    def do_ambiente(cls) -> "Config":
        token = os.environ.get("PRISMO_TOKEN", "")
        if len(token) < 16:
            raise RuntimeError("Defina PRISMO_TOKEN com pelo menos 16 caracteres.")
        supabase_url = os.environ.get("SUPABASE_URL") or None
        hosts = {h.strip().lower() for h in os.environ.get("PRISMO_HOSTS_PERMITIDOS", "").split(",") if h.strip()}
        if not hosts and supabase_url:
            hosts = {urlparse(supabase_url).hostname or ""}
        return cls(
            token=token,
            token_callback=os.environ.get("PRISMO_CALLBACK_TOKEN") or token,
            supabase_url=supabase_url,
            supabase_chave=os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or None,
            bucket_faixas=os.environ.get("PRISMO_BUCKET_FAIXAS", "stems"),
            bucket_resultados=os.environ.get("PRISMO_BUCKET_RESULTADOS", "results"),
            hosts_permitidos=hosts,
            hosts_callback={h.strip().lower() for h in os.environ.get("PRISMO_HOSTS_CALLBACK", "").split(",") if h.strip()} or hosts,
            max_bytes=int(float(os.environ.get("PRISMO_MAX_MB", "60")) * 1024 * 1024),
            trabalhadores=max(1, int(os.environ.get("PRISMO_TRABALHADORES", "1"))),
            dispositivo=os.environ.get("PRISMO_DISPOSITIVO") or None,
            pasta=Path(os.environ.get("PRISMO_PASTA", "/tmp/prismo")),
        )


# ---------------------------------------------------------------- modelos

class PedidoProcessamento(BaseModel):
    song_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    audio_url: str
    instrumento: Literal["guitarra", "violao", "baixo", "voz", "piano"] = "guitarra"
    letra: bool = True
    separar: bool = True
    callback_url: str | None = None
    nome_arquivo: str | None = Field(default=None, max_length=200)
    # Pasta dentro dos buckets onde os arquivos serão salvos (ex.: "<id do usuário>/<id da música>").
    # O Storage do site só deixa cada usuário abrir a própria pasta. Padrão: o song_id.
    pasta_destino: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{1,64}(/[A-Za-z0-9_-]{1,64}){0,2}$")
    # Links de envio assinados, um por arquivo, gerados pelo site (o motor não precisa de chave do Supabase).
    # Chaves: "faixas/<voz|guitarra|baixo|bateria|piano|outros>" e "arquivos/<cifra|tablatura|musicxml|midi>".
    uploads: dict[str, str] | None = Field(default=None, max_length=20)


@dataclass
class Trabalho:
    pedido: PedidoProcessamento
    status: str = "na_fila"  # na_fila | processando | concluido | erro
    etapa: str | None = None
    erro: str | None = None
    criado_em: float = field(default_factory=time.time)
    concluido_em: float | None = None

    def resumo(self) -> dict:
        return {
            "song_id": self.pedido.song_id,
            "status": self.status,
            "etapa": self.etapa,
            "mensagem": ETAPAS.get(self.etapa or "", None),
            "erro": self.erro,
            "criado_em": self.criado_em,
            "concluido_em": self.concluido_em,
        }


class ErroUsuario(Exception):
    """Erro com mensagem que pode ser mostrada ao usuário final."""


# ---------------------------------------------------------------- fila

class Fila:
    def __init__(self, config: Config, executar=None):
        self.config = config
        self._fila: "queue.Queue[Trabalho]" = queue.Queue()
        self._trabalhos: dict[str, Trabalho] = {}
        self._trava = threading.Lock()
        self._executar = executar or self._executar_trabalho
        self._threads: list[threading.Thread] = []

    def iniciar(self) -> None:
        for i in range(self.config.trabalhadores):
            t = threading.Thread(target=self._laco, name=f"prismo-trabalhador-{i}", daemon=True)
            t.start()
            self._threads.append(t)

    def adicionar(self, pedido: PedidoProcessamento) -> tuple[Trabalho, bool]:
        with self._trava:
            atual = self._trabalhos.get(pedido.song_id)
            if atual and atual.status in ("na_fila", "processando"):
                return atual, False
            trabalho = Trabalho(pedido)
            self._trabalhos[pedido.song_id] = trabalho
        self._fila.put(trabalho)
        return trabalho, True

    def obter(self, song_id: str) -> Trabalho | None:
        return self._trabalhos.get(song_id)

    def posicao(self, song_id: str) -> int:
        na_fila = [t for t in list(self._fila.queue)]
        for i, t in enumerate(na_fila):
            if t.pedido.song_id == song_id:
                return i + 1
        return 0

    @property
    def tamanho(self) -> int:
        return self._fila.qsize()

    def _laco(self) -> None:
        while True:
            trabalho = self._fila.get()
            try:
                self._executar(trabalho)
            except Exception:  # nunca deixa a thread morrer
                log.exception("Falha inesperada no trabalho %s", trabalho.pedido.song_id)
            finally:
                self._fila.task_done()

    # -------------------------------------------------- execução de um trabalho

    def _executar_trabalho(self, trabalho: Trabalho) -> None:
        cfg = self.config
        pedido = trabalho.pedido
        pasta = cfg.pasta / pedido.song_id
        trabalho.status = "processando"
        inicio = time.perf_counter()
        log.info("Processando %s (%s)", pedido.song_id, pedido.instrumento)

        def progresso(etapa: str) -> None:
            if etapa == trabalho.etapa:
                return
            trabalho.etapa = etapa
            self._chamar_callback(pedido, {"tipo": "progresso", "song_id": pedido.song_id,
                                           "etapa": etapa, "mensagem": ETAPAS.get(etapa, etapa)})

        try:
            shutil.rmtree(pasta, ignore_errors=True)
            pasta.mkdir(parents=True, exist_ok=True)
            progresso("preparo")
            arquivo = baixar_audio(pedido.audio_url, pasta, cfg.max_bytes, pedido.nome_arquivo)
            resultado = processar(
                str(arquivo),
                instrumento=pedido.instrumento,
                pasta_saida=str(pasta / "saida"),
                separar=pedido.separar,
                letra=pedido.letra,
                dispositivo=cfg.dispositivo,
                ao_progredir=progresso,
            )
            resultado["arquivo"] = pedido.nome_arquivo or resultado["arquivo"]
            resultado = self._publicar_arquivos(pedido.pasta_destino or pedido.song_id, resultado, pedido.uploads)
            resultado["tempo_total"] = round(time.perf_counter() - inicio, 1)
            trabalho.status = "concluido"
            trabalho.concluido_em = time.time()
            self._chamar_callback(pedido, {"tipo": "concluido", "song_id": pedido.song_id, "resultado": resultado},
                                  tentativas=5)
            log.info("Concluído %s em %.1fs", pedido.song_id, resultado["tempo_total"])
        except Exception as erro:
            mensagem = str(erro) if isinstance(erro, ErroUsuario) else (
                "Não foi possível processar esta música. Tente outro arquivo ou envie novamente em alguns minutos."
            )
            if not isinstance(erro, ErroUsuario):
                log.error("Erro em %s:\n%s", pedido.song_id, traceback.format_exc())
            trabalho.status = "erro"
            trabalho.erro = mensagem
            trabalho.concluido_em = time.time()
            self._chamar_callback(pedido, {"tipo": "erro", "song_id": pedido.song_id, "mensagem": mensagem},
                                  tentativas=5)
        finally:
            shutil.rmtree(pasta, ignore_errors=True)

    def _publicar_arquivos(self, pasta: str, resultado: dict, uploads: dict[str, str] | None = None) -> dict:
        """Envia faixas e materiais ao Storage e troca os caminhos locais pelos do Storage.

        Com `uploads` (links assinados do site), cada arquivo vai para o seu link. Sem eles,
        usa a chave de serviço do Supabase, se estiver configurada.
        """
        cfg = self.config
        if uploads:
            faixas, arquivos = {}, {}
            for nome, caminho in resultado.get("faixas", {}).items():
                link = uploads.get(f"faixas/{nome}")
                if link:
                    faixas[nome] = enviar_por_link(link, comprimir_para_mp3(Path(caminho)))
            for tipo, caminho in resultado.get("arquivos", {}).items():
                link = uploads.get(f"arquivos/{tipo}")
                if link:
                    arquivos[tipo] = enviar_por_link(link, Path(caminho))
            resultado["faixas"] = faixas
            resultado["arquivos"] = arquivos
            resultado["buckets"] = {"faixas": cfg.bucket_faixas, "arquivos": cfg.bucket_resultados}
            return resultado
        if not (cfg.supabase_url and cfg.supabase_chave):
            log.warning("Supabase não configurado: os arquivos ficam só no servidor e serão apagados.")
            resultado["faixas"] = {}
            resultado["arquivos"] = {}
            resultado["avisos"].append("Armazenamento não configurado no motor: faixas e arquivos não foram salvos.")
            return resultado
        supabase = Supabase(cfg.supabase_url, cfg.supabase_chave)

        faixas = {}
        for nome, caminho in resultado.get("faixas", {}).items():
            arquivo = comprimir_para_mp3(Path(caminho))
            faixas[nome] = supabase.enviar(cfg.bucket_faixas, f"{pasta}/{nome}{arquivo.suffix}", arquivo)
        arquivos = {}
        for tipo, caminho in resultado.get("arquivos", {}).items():
            arquivo = Path(caminho)
            arquivos[tipo] = supabase.enviar(cfg.bucket_resultados, f"{pasta}/{arquivo.name}", arquivo)

        resultado["faixas"] = faixas
        resultado["arquivos"] = arquivos
        resultado["buckets"] = {"faixas": cfg.bucket_faixas, "arquivos": cfg.bucket_resultados}
        return resultado

    def _chamar_callback(self, pedido: PedidoProcessamento, corpo: dict, tentativas: int = 1) -> None:
        if not pedido.callback_url:
            return
        cabecalhos = {"Authorization": f"Bearer {self.config.token_callback}"}
        for tentativa in range(1, tentativas + 1):
            try:
                r = httpx.post(pedido.callback_url, json=corpo, headers=cabecalhos, timeout=30)
                if r.status_code < 300:
                    return
                log.warning("Callback respondeu %s (tentativa %s): %s", r.status_code, tentativa, r.text[:200])
            except httpx.HTTPError as e:
                log.warning("Callback falhou (tentativa %s): %s", tentativa, e)
            if tentativa < tentativas:
                time.sleep(min(2 ** tentativa, 30))


# ---------------------------------------------------------------- download

def baixar_audio(url: str, pasta: Path, max_bytes: int, nome_arquivo: str | None = None) -> Path:
    extensao = Path(urlparse(url).path).suffix.lower()
    if nome_arquivo and Path(nome_arquivo).suffix.lower() in EXTENSOES_ACEITAS:
        extensao = Path(nome_arquivo).suffix.lower()
    try:
        with httpx.stream("GET", url, timeout=60, follow_redirects=False) as r:
            if r.status_code != 200:
                raise ErroUsuario("Não foi possível baixar o arquivo enviado. Envie a música novamente.")
            if extensao not in EXTENSOES_ACEITAS:
                tipo = r.headers.get("content-type", "").split(";")[0].strip().lower()
                extensao = TIPO_PARA_EXTENSAO.get(tipo, "")
            if extensao not in EXTENSOES_ACEITAS:
                raise ErroUsuario("Formato de arquivo não suportado. Envie MP3, WAV, M4A, OGG, FLAC, MP4, MOV ou WEBM.")
            declarado = int(r.headers.get("content-length") or 0)
            if declarado > max_bytes:
                raise ErroUsuario(f"O arquivo passa do limite de {max_bytes // (1024 * 1024)} MB.")
            destino = pasta / f"entrada{extensao}"
            total = 0
            with destino.open("wb") as f:
                for bloco in r.iter_bytes(1024 * 256):
                    total += len(bloco)
                    if total > max_bytes:
                        raise ErroUsuario(f"O arquivo passa do limite de {max_bytes // (1024 * 1024)} MB.")
                    f.write(bloco)
    except httpx.HTTPError as erro:
        raise ErroUsuario("Não foi possível baixar o arquivo enviado. Envie a música novamente.") from erro
    if total == 0:
        raise ErroUsuario("O arquivo enviado está vazio.")
    return destino


# ---------------------------------------------------------------- app

def _host_permitido(url: str, hosts: set[str]) -> bool:
    partes = urlparse(url)
    if partes.scheme != "https" or not partes.hostname:
        return False
    return not hosts or partes.hostname.lower() in hosts


def _recursos() -> dict:
    def existe(modulo: str) -> bool:
        import importlib.util
        return importlib.util.find_spec(modulo) is not None

    gpu = False
    if existe("torch"):
        try:
            import torch
            gpu = bool(torch.cuda.is_available())
        except Exception:
            gpu = False
    return {
        "separacao": existe("demucs"),
        "transcricao": existe("basic_pitch"),
        "letra": existe("faster_whisper"),
        "ffmpeg": shutil.which("ffmpeg") is not None,
        "gpu": gpu,
    }


def criar_app(config: Config | None = None, fila: Fila | None = None) -> FastAPI:
    config = config or Config.do_ambiente()
    fila = fila or Fila(config)

    @asynccontextmanager
    async def ciclo_de_vida(_app: FastAPI):
        config.pasta.mkdir(parents=True, exist_ok=True)
        fila.iniciar()
        yield

    app = FastAPI(title="Prismo · motor de áudio", version=__version__, lifespan=ciclo_de_vida)
    app.state.config = config
    app.state.fila = fila

    def autenticar(authorization: str = Header(default="")) -> None:
        esperado = f"Bearer {config.token}"
        if not hmac.compare_digest(authorization.encode(), esperado.encode()):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido.")

    @app.get("/saude")
    def saude() -> dict:
        return {"ok": True, "versao": __version__, "fila": fila.tamanho, "recursos": _recursos()}

    @app.post("/processar", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(autenticar)])
    def processar_musica(pedido: PedidoProcessamento) -> dict:
        if not _host_permitido(pedido.audio_url, config.hosts_permitidos):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "audio_url precisa ser https e de um host permitido.")
        if pedido.callback_url and not _host_permitido(pedido.callback_url, config.hosts_callback):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "callback_url precisa ser https e de um host permitido.")
        for chave, link in (pedido.uploads or {}).items():
            if not chave.startswith(("faixas/", "arquivos/")) or not _host_permitido(link, config.hosts_permitidos):
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "uploads precisa ter links https de um host permitido.")
            try:
                caminho_do_link(link)
            except Exception:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Link de envio inválido em {chave}.")
        trabalho, novo = fila.adicionar(pedido)
        resposta = trabalho.resumo()
        resposta["novo"] = novo
        resposta["posicao_na_fila"] = fila.posicao(pedido.song_id)
        return resposta

    @app.get("/status/{song_id}", dependencies=[Depends(autenticar)])
    def ver_status(song_id: str) -> dict:
        trabalho = fila.obter(song_id)
        if not trabalho:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Música não encontrada na fila deste servidor.")
        resposta = trabalho.resumo()
        resposta["posicao_na_fila"] = fila.posicao(song_id)
        return resposta

    return app


def carregar_env(caminho: str = ".env") -> None:
    """Lê um arquivo .env simples (CHAVE=valor) sem sobrescrever o ambiente."""
    arquivo = Path(caminho)
    if not arquivo.exists():
        return
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        valor = valor.strip().strip('"').strip("'")
        if valor:
            os.environ.setdefault(chave.strip(), valor)


def main() -> None:
    import uvicorn

    carregar_env()
    porta = int(os.environ.get("PORT", "8000"))
    uvicorn.run(criar_app(), host="0.0.0.0", port=porta)


if __name__ == "__main__":
    main()
