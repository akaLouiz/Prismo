"""Pipeline completo: arquivo enviado -> faixas, análise, cifra, tablatura e partitura."""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np

from . import ia
from .analise import analisar, carregar_audio
from .cifra import gerar_cifra, limpar_acordes
from .models import Nota, Palavra
from .tablatura import gerar_tablatura, renderizar_tablatura
from .teoria import nome_acorde, nome_tonalidade, sugerir_capotraste

INSTRUMENTOS = {
    # instrumento: faixa do Demucs que contém ele
    "guitarra": "guitarra",
    "violao": "guitarra",
    "baixo": "baixo",
    "voz": "voz",
    "piano": "piano",
}
COM_TABLATURA = {"guitarra", "violao", "baixo"}
FAIXAS_HARMONICAS = ("guitarra", "baixo", "piano", "outros")


def _log(msg: str) -> None:
    print(f"[prismo] {msg}", flush=True)


def processar(
    arquivo: str,
    instrumento: str = "guitarra",
    pasta_saida: str | None = None,
    separar: bool = True,
    letra: bool = True,
    transcrever: bool = True,
    dispositivo: str | None = None,
) -> dict:
    if instrumento not in INSTRUMENTOS:
        raise ValueError(f"Instrumento desconhecido: {instrumento}. Opções: {', '.join(INSTRUMENTOS)}")
    origem = Path(arquivo)
    saida = Path(pasta_saida or f"saida/{origem.stem}")
    saida.mkdir(parents=True, exist_ok=True)
    avisos: list[str] = []
    tempos: dict[str, float] = {}
    relogio = time.perf_counter()

    def marcar(etapa: str) -> None:
        nonlocal relogio
        agora = time.perf_counter()
        tempos[etapa] = round(agora - relogio, 2)
        relogio = agora

    audio = ia.extrair_audio(str(origem), saida)
    marcar("preparo")

    # 1. Separação
    faixas: dict[str, Path] = {}
    if separar:
        _log("Separando as faixas (pode levar alguns minutos sem GPU)...")
        try:
            faixas = ia.separar_faixas(str(audio), saida / "faixas", dispositivo)
        except ia.DependenciaAusente as e:
            avisos.append(f"Separação não executada: {e}")
        marcar("separacao")

    # 2. Análise musical
    _log("Analisando tom, andamento e acordes...")
    mistura, sr = carregar_audio(str(audio))
    harmonia = None
    presentes = [faixas[f] for f in FAIXAS_HARMONICAS if f in faixas]
    if presentes:
        sinais = [carregar_audio(str(p))[0] for p in presentes]
        n = min(len(s) for s in sinais)
        harmonia = np.sum([s[:n] for s in sinais], axis=0)
    analise = analisar(mistura, sr, sinal_harmonia=harmonia)
    analise.acordes = limpar_acordes(analise.acordes)
    marcar("analise")

    # 3. Letra
    palavras: list[Palavra] = []
    if letra and "voz" in faixas:
        _log("Reconhecendo a letra na voz isolada...")
        try:
            palavras = ia.transcrever_letra(str(faixas["voz"]))
        except ia.DependenciaAusente as e:
            avisos.append(f"Letra não reconhecida: {e}")
        marcar("letra")

    # 4. Transcrição do instrumento escolhido
    notas: list[Nota] = []
    if transcrever:
        faixa = faixas.get(INSTRUMENTOS[instrumento], audio)
        if faixa == audio and faixas:
            avisos.append(f"A faixa de {instrumento} não foi encontrada; transcrevendo a mistura.")
        _log(f"Transcrevendo as notas de {instrumento}...")
        try:
            notas = ia.transcrever_notas(str(faixa), instrumento)
        except ia.DependenciaAusente as e:
            avisos.append(f"Transcrição não executada: {e}")
        marcar("transcricao")

    # 5. Materiais
    arquivos: dict[str, str] = {}
    primeira_batida = analise.batidas[0] if analise.batidas else None
    cifra = gerar_cifra(
        analise.acordes, analise.tonalidade, analise.bpm, palavras or None,
        titulo=origem.stem, inicio_compassos=primeira_batida,
    )
    (saida / "cifra.txt").write_text(cifra, encoding="utf-8")
    arquivos["cifra"] = str(saida / "cifra.txt")

    eventos_tab = []
    if notas and instrumento in COM_TABLATURA:
        eventos_tab = gerar_tablatura(notas, instrumento)
        inicio = analise.batidas[0] if analise.batidas else 0.0
        tab = renderizar_tablatura(eventos_tab, analise.bpm, instrumento, inicio_musica=inicio)
        (saida / "tablatura.txt").write_text(tab, encoding="utf-8")
        arquivos["tablatura"] = str(saida / "tablatura.txt")

    if notas:
        from .partitura import criar_partitura, exportar

        partitura = criar_partitura(notas, analise.bpm, analise.tonalidade, instrumento, titulo=origem.stem)
        arquivos.update(exportar(partitura, str(saida / "partitura")))
    marcar("materiais")

    tom = analise.tonalidade
    resultado = {
        "arquivo": origem.name,
        "instrumento": instrumento,
        "duracao": analise.duracao,
        "bpm": analise.bpm,
        "compasso": analise.compasso,
        "tom": {
            "cifra": nome_tonalidade(tom),
            "nome": nome_tonalidade(tom, em_portugues=True),
            "confianca": tom.confianca,
        },
        "capotraste": sugerir_capotraste(analise.acordes),
        "acordes": [
            {"inicio": round(a.inicio, 3), "fim": round(a.fim, 3), "nome": nome_acorde(a, tom), "confianca": a.confianca}
            for a in analise.acordes
        ],
        "batidas": analise.batidas,
        "faixas": {nome: str(p) for nome, p in faixas.items()},
        "letra": [asdict(p) for p in palavras],
        "notas": [asdict(n) for n in notas],
        "tablatura": [
            {"inicio": round(e.inicio, 3), "fim": round(e.fim, 3), "posicoes": [asdict(p) for p in e.posicoes]}
            for e in eventos_tab
        ],
        "arquivos": arquivos,
        "avisos": avisos,
        "tempo_por_etapa": tempos,
    }
    (saida / "resultado.json").write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    _log(f"Pronto. Resultados em {saida}")
    for aviso in avisos:
        _log(f"Aviso: {aviso}")
    return resultado
