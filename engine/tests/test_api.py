from pathlib import Path

import httpx
import pytest
import soundfile as sf

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from prismo_engine import api  # noqa: E402
from sintetico import SR, gerar_progressao  # noqa: E402

TOKEN = "token-de-teste-com-mais-de-16"
HOST = "projeto.supabase.co"
AUDIO = f"https://{HOST}/storage/v1/object/sign/uploads/u1/musica.wav?token=abc"
CALLBACK = f"https://{HOST}/functions/v1/engine-callback"


def config(tmp_path: Path, supabase: bool = True) -> api.Config:
    return api.Config(
        token=TOKEN,
        token_callback="segredo-do-callback",
        supabase_url=f"https://{HOST}" if supabase else None,
        supabase_chave="chave-servico" if supabase else None,
        bucket_faixas="stems",
        bucket_resultados="results",
        hosts_permitidos={HOST},
        hosts_callback={HOST, "prismo.app"},
        max_bytes=5 * 1024 * 1024,
        trabalhadores=1,
        dispositivo=None,
        pasta=tmp_path / "trabalho",
    )


def pedido(**extra) -> dict:
    corpo = {"song_id": "musica-123", "audio_url": AUDIO, "instrumento": "violao",
             "letra": False, "separar": False, "callback_url": CALLBACK, "nome_arquivo": "ensaio.wav"}
    corpo.update(extra)
    return corpo


@pytest.fixture
def cliente(tmp_path):
    executados = []
    fila = api.Fila(config(tmp_path), executar=executados.append)
    app = api.criar_app(config(tmp_path), fila)
    with TestClient(app) as c:
        c.executados = executados
        yield c


AUTH = {"Authorization": f"Bearer {TOKEN}"}


# ---------------------------------------------------------------- rotas

def test_saude_e_publica(cliente):
    r = cliente.get("/saude")
    assert r.status_code == 200 and r.json()["ok"] is True
    assert set(r.json()["recursos"]) == {"separacao", "transcricao", "letra", "ffmpeg", "gpu"}


def test_processar_exige_token(cliente):
    assert cliente.post("/processar", json=pedido()).status_code == 401
    assert cliente.post("/processar", json=pedido(), headers={"Authorization": "Bearer errado"}).status_code == 401


@pytest.mark.parametrize("campo,url", [
    ("audio_url", "https://site-qualquer.com/musica.mp3"),
    ("audio_url", f"http://{HOST}/musica.mp3"),
    ("callback_url", "https://outro-host.com/callback"),
])
def test_bloqueia_enderecos_nao_permitidos(cliente, campo, url):
    r = cliente.post("/processar", json=pedido(**{campo: url}), headers=AUTH)
    assert r.status_code == 400


def test_valida_campos(cliente):
    assert cliente.post("/processar", json=pedido(instrumento="flauta"), headers=AUTH).status_code == 422
    assert cliente.post("/processar", json=pedido(song_id="../etc"), headers=AUTH).status_code == 422


def test_enfileira_e_nao_duplica(cliente, monkeypatch):
    fila = cliente.app.state.fila
    monkeypatch.setattr(fila, "iniciar", lambda: None)
    r = cliente.post("/processar", json=pedido(), headers=AUTH)
    assert r.status_code == 202 and r.json()["status"] in ("na_fila", "processando")
    r2 = cliente.post("/processar", json=pedido(), headers=AUTH)
    assert r2.status_code == 202
    s = cliente.get("/status/musica-123", headers=AUTH)
    assert s.status_code == 200 and s.json()["song_id"] == "musica-123"
    assert cliente.get("/status/nao-existe", headers=AUTH).status_code == 404


# ---------------------------------------------------------------- execução real

@pytest.fixture
def ambiente_trabalho(tmp_path, monkeypatch):
    """Simula download, Supabase e callback; o processamento é o de verdade."""
    sinal, _ = gerar_progressao(bpm=92, repeticoes=2)
    wav = tmp_path / "fonte.wav"
    sf.write(wav, sinal, SR)

    def baixar(url, pasta, max_bytes, nome=None):
        destino = pasta / "entrada.wav"
        destino.write_bytes(wav.read_bytes())
        return destino

    enviados, callbacks = [], []
    monkeypatch.setattr(api, "baixar_audio", baixar)
    monkeypatch.setattr(api.Supabase, "enviar", lambda self, bucket, caminho, arquivo: enviados.append((bucket, caminho)) or caminho)
    monkeypatch.setattr(api.Fila, "_chamar_callback", lambda self, p, corpo, tentativas=1: callbacks.append(corpo))
    return enviados, callbacks


def test_fluxo_completo(tmp_path, ambiente_trabalho):
    enviados, callbacks = ambiente_trabalho
    fila = api.Fila(config(tmp_path))
    trabalho = api.Trabalho(api.PedidoProcessamento(**pedido()))
    fila._executar_trabalho(trabalho)

    assert trabalho.status == "concluido", trabalho.erro
    etapas = [c["etapa"] for c in callbacks if c["tipo"] == "progresso"]
    assert etapas[0] == "preparo" and "analise" in etapas and etapas[-1] == "materiais"
    assert len(etapas) == len(set(etapas))  # cada etapa avisada uma vez

    final = callbacks[-1]
    assert final["tipo"] == "concluido" and final["song_id"] == "musica-123"
    r = final["resultado"]
    assert r["tom"]["cifra"] == "Em" and abs(r["bpm"] - 92) < 4
    assert [a["nome"] for a in r["acordes"]][:4] == ["Em", "C", "G", "D"]
    assert r["arquivo"] == "ensaio.wav"
    assert r["arquivos"]["cifra"] == "musica-123/cifra.txt"
    assert r["buckets"] == {"faixas": "stems", "arquivos": "results"}
    assert ("results", "musica-123/cifra.txt") in enviados
    assert not (tmp_path / "trabalho" / "musica-123").exists()  # pasta temporária apagada


def test_erro_amigavel_quando_download_falha(tmp_path, ambiente_trabalho, monkeypatch):
    _, callbacks = ambiente_trabalho

    def falha(*a, **k):
        raise api.ErroUsuario("Não foi possível baixar o arquivo enviado. Envie a música novamente.")

    monkeypatch.setattr(api, "baixar_audio", falha)
    fila = api.Fila(config(tmp_path))
    trabalho = api.Trabalho(api.PedidoProcessamento(**pedido()))
    fila._executar_trabalho(trabalho)
    assert trabalho.status == "erro"
    assert callbacks[-1] == {"tipo": "erro", "song_id": "musica-123",
                             "mensagem": "Não foi possível baixar o arquivo enviado. Envie a música novamente."}


def test_erro_interno_nao_vaza_detalhes(tmp_path, ambiente_trabalho, monkeypatch):
    _, callbacks = ambiente_trabalho
    monkeypatch.setattr(api, "processar", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("segredo interno /var/x")))
    fila = api.Fila(config(tmp_path))
    fila._executar_trabalho(api.Trabalho(api.PedidoProcessamento(**pedido())))
    assert "segredo" not in callbacks[-1]["mensagem"]


# ---------------------------------------------------------------- download

def _servidor_falso(monkeypatch, corpo: bytes, tipo="audio/mpeg", status_code=200, tamanho=None):
    def responder(request):
        cabecalhos = {"content-type": tipo}
        if tamanho is not None:
            cabecalhos["content-length"] = str(tamanho)
        return httpx.Response(status_code, content=corpo, headers=cabecalhos)

    cliente = httpx.Client(transport=httpx.MockTransport(responder))
    monkeypatch.setattr(api.httpx, "stream", lambda metodo, url, **k: cliente.stream(metodo, url))


def test_download_usa_tipo_do_arquivo(tmp_path, monkeypatch):
    _servidor_falso(monkeypatch, b"ID3" + b"0" * 100, tipo="audio/mpeg")
    destino = api.baixar_audio("https://h/obj/sign/abc?token=1", tmp_path, 1024 * 1024)
    assert destino.suffix == ".mp3" and destino.stat().st_size == 103


def test_download_respeita_limite(tmp_path, monkeypatch):
    _servidor_falso(monkeypatch, b"0" * 2048)
    with pytest.raises(api.ErroUsuario, match="limite"):
        api.baixar_audio("https://h/musica.mp3", tmp_path, 1024)


def test_download_recusa_formato_desconhecido(tmp_path, monkeypatch):
    _servidor_falso(monkeypatch, b"<html>", tipo="text/html")
    with pytest.raises(api.ErroUsuario, match="Formato"):
        api.baixar_audio("https://h/pagina", tmp_path, 1024 * 1024)


def test_download_erro_http(tmp_path, monkeypatch):
    _servidor_falso(monkeypatch, b"", status_code=403)
    with pytest.raises(api.ErroUsuario, match="baixar"):
        api.baixar_audio("https://h/musica.mp3", tmp_path, 1024 * 1024)


def test_carrega_env_sem_sobrescrever(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("# comentário\nPRISMO_X_TESTE=do-arquivo\nPRISMO_Y_TESTE='aspas'\nVAZIA=\n", encoding="utf-8")
    monkeypatch.setenv("PRISMO_X_TESTE", "do-ambiente")
    monkeypatch.delenv("PRISMO_Y_TESTE", raising=False)
    api.carregar_env(str(env))
    import os
    assert os.environ["PRISMO_X_TESTE"] == "do-ambiente"
    assert os.environ["PRISMO_Y_TESTE"] == "aspas"
    assert "VAZIA" not in os.environ


def test_salva_na_pasta_do_usuario(tmp_path, ambiente_trabalho):
    enviados, callbacks = ambiente_trabalho
    fila = api.Fila(config(tmp_path))
    pasta = "11111111-aaaa/musica-123"
    fila._executar_trabalho(api.Trabalho(api.PedidoProcessamento(**pedido(pasta_destino=pasta))))
    r = callbacks[-1]["resultado"]
    assert r["arquivos"]["cifra"] == f"{pasta}/cifra.txt"
    assert all(caminho.startswith(pasta + "/") for _, caminho in enviados)


def test_pasta_destino_invalida(cliente):
    for ruim in ("../outro", "a/b/c/d", "a b", "/raiz"):
        assert cliente.post("/processar", json=pedido(pasta_destino=ruim), headers=AUTH).status_code == 422


def test_callback_no_dominio_do_site(cliente, monkeypatch):
    monkeypatch.setattr(cliente.app.state.fila, "iniciar", lambda: None)
    ok = cliente.post("/processar", json=pedido(callback_url="https://prismo.app/api/public/engine-callback"), headers=AUTH)
    assert ok.status_code == 202
    # o domínio do site vale só para o callback, não para baixar áudio
    ruim = cliente.post("/processar", json=pedido(audio_url="https://prismo.app/musica.mp3", song_id="outra"), headers=AUTH)
    assert ruim.status_code == 400
