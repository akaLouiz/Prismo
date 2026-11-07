"""Análise musical: andamento, tonalidade e acordes.

Abordagem clássica e leve (roda em CPU, sem baixar modelos):
- BPM e batidas: rastreador de batidas do librosa.
- Tonalidade: perfis de Krumhansl-Schmuckler sobre o cromagrama médio.
- Acordes: cromagrama sincronizado com as batidas, comparação com modelos de
  acordes e suavização com Viterbi (evita acordes "piscando" a cada batida).

Isto é a linha de base. Mais à frente, um modelo treinado de reconhecimento de
acordes pode substituir `detectar_acordes` sem mudar o resto do motor.
"""

from __future__ import annotations

import numpy as np
import librosa

from .models import Acorde, Analise, Tonalidade
from . import ritmo

TAXA = 22050
SALTO = 512

# Perfis de Krumhansl-Kessler (peso de cada grau da escala)
_PERFIL_MAIOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
_PERFIL_MENOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

# Intervalos (em semitons a partir da raiz) e peso de cada nota no modelo do acorde
_QUALIDADES = {
    "maj": {0: 1.0, 4: 1.0, 7: 1.0},
    "min": {0: 1.0, 3: 1.0, 7: 1.0},
    "7": {0: 1.0, 4: 1.0, 7: 1.0, 10: 0.7},
    "maj7": {0: 1.0, 4: 1.0, 7: 1.0, 11: 0.7},
    "min7": {0: 1.0, 3: 1.0, 7: 1.0, 10: 0.7},
}


def carregar_audio(caminho: str, taxa: int = TAXA) -> tuple[np.ndarray, int]:
    sinal, sr = librosa.load(caminho, sr=taxa, mono=True)
    return sinal, sr


def _modelos_de_acordes() -> tuple[np.ndarray, list[tuple[int | None, str]]]:
    modelos, rotulos = [], []
    for qualidade, notas in _QUALIDADES.items():
        for raiz in range(12):
            v = np.zeros(12)
            for intervalo, peso in notas.items():
                v[(raiz + intervalo) % 12] = peso
            modelos.append(v / np.linalg.norm(v))
            rotulos.append((raiz, qualidade))
    # "Sem acorde": vetor uniforme, vence em silêncio ou ruído
    v = np.ones(12) / np.sqrt(12)
    modelos.append(v)
    rotulos.append((None, "N"))
    return np.array(modelos), rotulos


def detectar_tonalidade(croma: np.ndarray) -> Tonalidade:
    """Recebe cromagrama (12 x quadros) e devolve a tonalidade mais provável."""
    perfil = croma.mean(axis=1)
    if perfil.sum() == 0:
        return Tonalidade(0, "maior", 0.0)
    pontuacoes = []
    for tonica in range(12):
        for modo, ref in (("maior", _PERFIL_MAIOR), ("menor", _PERFIL_MENOR)):
            r = np.corrcoef(perfil, np.roll(ref, tonica))[0, 1]
            pontuacoes.append((r, tonica, modo))
    pontuacoes.sort(reverse=True)
    melhor, segundo = pontuacoes[0], pontuacoes[1]
    confianca = float(max(0.0, melhor[0] - segundo[0]) + max(0.0, melhor[0])) / 2
    return Tonalidade(melhor[1], melhor[2], round(confianca, 3))


def refinar_tonalidade(tom: Tonalidade, acordes: list[Acorde]) -> Tonalidade:
    """Desempata tons relativos (Sol maior x Mi menor), que têm as mesmas notas.

    Compara quanto a música "repousa" no acorde da tônica de cada um: tempo
    total em cada acorde, com peso extra para o primeiro e o último acorde,
    que costumam ser a tônica.
    """
    if tom.modo == "maior":
        maior, menor = tom.tonica, (tom.tonica + 9) % 12
    else:
        menor, maior = tom.tonica, (tom.tonica + 3) % 12
    validos = [a for a in acordes if a.raiz is not None]
    if not validos:
        return tom

    def peso(raiz: int, qualidades: set[str]) -> float:
        p = sum(a.fim - a.inicio for a in validos if a.raiz == raiz and a.qualidade in qualidades)
        total = sum(a.fim - a.inicio for a in validos) or 1.0
        p /= total
        for a in (validos[0], validos[-1]):
            if a.raiz == raiz and a.qualidade in qualidades:
                p += 0.25
        return p

    p_maior = peso(maior, {"maj", "maj7"})
    p_menor = peso(menor, {"min", "min7"})
    if p_menor > p_maior and tom.modo == "maior":
        return Tonalidade(menor, "menor", tom.confianca)
    if p_maior > p_menor and tom.modo == "menor":
        return Tonalidade(maior, "maior", tom.confianca)
    return tom


def _viterbi(emissao: np.ndarray, permanencia: float) -> np.ndarray:
    """Caminho mais provável de estados. emissao: (estados x passos), em probabilidades."""
    n_estados, n_passos = emissao.shape
    log_e = np.log(emissao + 1e-12)
    troca = (1.0 - permanencia) / (n_estados - 1)
    log_t = np.full((n_estados, n_estados), np.log(troca))
    np.fill_diagonal(log_t, np.log(permanencia))

    pontos = np.zeros((n_estados, n_passos))
    volta = np.zeros((n_estados, n_passos), dtype=int)
    pontos[:, 0] = log_e[:, 0] - np.log(n_estados)
    for t in range(1, n_passos):
        cand = pontos[:, t - 1][:, None] + log_t  # (de, para)
        volta[:, t] = cand.argmax(axis=0)
        pontos[:, t] = cand.max(axis=0) + log_e[:, t]

    caminho = np.zeros(n_passos, dtype=int)
    caminho[-1] = pontos[:, -1].argmax()
    for t in range(n_passos - 1, 0, -1):
        caminho[t - 1] = volta[caminho[t], t]
    return caminho


def detectar_acordes(
    croma_batidas: np.ndarray,
    tempos_batidas: np.ndarray,
    duracao: float,
    nitidez: float = 18.0,
    permanencia: float = 0.85,
    croma_baixo: np.ndarray | None = None,
    peso_baixo: float = 0.12,
    piso_clareza: float = 1.0,
    suavizar: bool = False,
) -> list[Acorde]:
    """Acordes por batida, suavizados e unidos em trechos.

    Com a faixa do baixo isolada (`croma_baixo`), a nota mais forte do baixo indica a
    fundamental, e os acordes com essa raiz ganham um bônus, como um músico faz ao ouvir.
    É o que mais protege contra solos e dedilhados: nos testes com solo sobre acordes,
    os acertos por compasso foram de 70% para 93%.

    `piso_clareza` < 1 deixa a decisão "frouxa" quando o som não parece acorde, e
    `suavizar` mistura batidas vizinhas. Os dois ficam desligados por padrão porque não
    melhoraram os testes; estão aqui para novos ajustes.
    """
    if croma_batidas.shape[1] == 0:
        return []
    modelos, rotulos = _modelos_de_acordes()
    # Suaviza levemente entre batidas vizinhas: notas de passagem pesam menos
    if suavizar and croma_batidas.shape[1] >= 3:
        croma_batidas = 0.25 * np.roll(croma_batidas, 1, axis=1) + 0.5 * croma_batidas + 0.25 * np.roll(croma_batidas, -1, axis=1)
    normas = np.linalg.norm(croma_batidas, axis=0, keepdims=True)
    croma_n = croma_batidas / np.maximum(normas, 1e-9)
    similaridade = modelos @ croma_n  # (acordes x batidas)
    # O modelo uniforme parece com qualquer coisa; só deve vencer com folga
    similaridade[-1] *= 0.8

    if croma_baixo is not None and croma_baixo.shape[1] == croma_batidas.shape[1]:
        baixo_n = croma_baixo / np.maximum(croma_baixo.max(axis=0, keepdims=True), 1e-9)
        for k, (raiz, _) in enumerate(rotulos):
            if raiz is not None:
                similaridade[k] += peso_baixo * baixo_n[raiz]

    # Batidas quase silenciosas puxam para "sem acorde"
    silencio = (normas[0] < 1e-3)
    similaridade[-1, silencio] = 1.0

    # Clareza harmônica: acorde bem definido ~0,9+; nota solta ~0,6
    clareza = similaridade[:-1].max(axis=0)
    fator = np.clip((clareza - 0.6) / (0.85 - 0.6), piso_clareza, 1.0)
    emissao = np.exp(nitidez * fator * (similaridade - similaridade.max(axis=0, keepdims=True)))
    emissao /= emissao.sum(axis=0, keepdims=True)
    caminho = _viterbi(emissao, permanencia)

    limites = list(tempos_batidas) + [duracao]
    acordes: list[Acorde] = []
    for i, estado in enumerate(caminho):
        raiz, qualidade = rotulos[estado]
        inicio, fim = float(limites[i]), float(limites[i + 1])
        conf = float(emissao[estado, i])
        if acordes and acordes[-1].raiz == raiz and acordes[-1].qualidade == qualidade:
            anterior = acordes[-1]
            peso = anterior.fim - anterior.inicio
            anterior.confianca = (anterior.confianca * peso + conf * (fim - inicio)) / (peso + fim - inicio)
            anterior.fim = fim
        else:
            acordes.append(Acorde(inicio, fim, raiz, qualidade, conf))
    for a in acordes:
        a.confianca = round(a.confianca, 3)
    return acordes


def analisar(
    sinal: np.ndarray,
    sr: int = TAXA,
    sinal_harmonia: np.ndarray | None = None,
    sinal_baixo: np.ndarray | None = None,
    sinal_bateria: np.ndarray | None = None,
) -> Analise:
    """Análise completa de uma faixa.

    `sinal` é a mistura (bom para achar o pulso). `sinal_harmonia`, se vier, é
    a soma das faixas harmônicas já separadas (sem voz e bateria), que dá
    acordes e tonalidade bem mais limpos. `sinal_baixo` e `sinal_bateria`
    (faixas isoladas) ajudam a achar o "1" do compasso.
    """
    duracao = float(len(sinal) / sr)
    harmonico, percussivo = librosa.effects.hpss(sinal)
    if sinal_harmonia is not None:
        harmonico = sinal_harmonia[: len(sinal)]
    pulso = percussivo if np.abs(percussivo).sum() > 0 else sinal

    # Batidas: rastreador do librosa + correções de andamento e de bordas (ver ritmo.py)
    _, quadros_batida = librosa.beat.beat_track(y=pulso, sr=sr, hop_length=SALTO)
    tempos_batidas = librosa.frames_to_time(quadros_batida, sr=sr, hop_length=SALTO)
    fonte_grave = sinal_bateria if sinal_bateria is not None and np.abs(sinal_bateria).sum() > 0 else pulso
    grave, t_grave = ritmo.envelope_de_ataques(fonte_grave[: len(sinal)], sr, fmax=150.0)
    # Dobrar o andamento só com evidência da bateria: graves (bumbo) e, com a bateria
    # isolada, todas as frequências. Na mistura, um solo em colcheias enganaria o teste.
    evidencias = [(grave, t_grave)]
    if sinal_bateria is not None and np.abs(sinal_bateria).sum() > 0:
        evidencias.append(ritmo.envelope_de_ataques(sinal_bateria[: len(sinal)], sr))
    tempos_batidas = ritmo.corrigir_andamento(tempos_batidas, evidencias)
    tempos_batidas = ritmo.completar_bordas(tempos_batidas, sinal, sr)
    bpm = ritmo.bpm_das_batidas(tempos_batidas, 120.0)

    croma = librosa.feature.chroma_cqt(y=harmonico, sr=sr, hop_length=SALTO)
    tonalidade = detectar_tonalidade(croma)

    quadros_batida = librosa.time_to_frames(tempos_batidas, sr=sr, hop_length=SALTO)
    if len(quadros_batida) < 2:
        # Sem pulso claro (ex.: rubato): usa janelas fixas de meio segundo
        quadros_batida = np.arange(0, croma.shape[1], int(0.5 * sr / SALTO))
    quadros_batida = np.unique(np.clip(quadros_batida, 0, croma.shape[1] - 1))
    limites = np.concatenate([[0], quadros_batida]) if quadros_batida[0] > 0 else quadros_batida
    croma_batidas = librosa.util.sync(croma, limites, aggregate=np.median)
    tempos = librosa.frames_to_time(limites, sr=sr, hop_length=SALTO)
    croma_batidas = croma_batidas[:, : len(tempos)]

    croma_baixo = None
    if sinal_baixo is not None and np.abs(sinal_baixo).sum() > 0:
        b = librosa.feature.chroma_cqt(y=sinal_baixo[: len(sinal)], sr=sr, hop_length=SALTO, fmin=librosa.note_to_hz("E1"))
        b = b[:, : croma.shape[1]]
        croma_baixo = librosa.util.sync(b, limites, aggregate=np.median)[:, : croma_batidas.shape[1]]
    acordes = detectar_acordes(croma_batidas, tempos, duracao, croma_baixo=croma_baixo)
    tonalidade = refinar_tonalidade(tonalidade, acordes)

    # O "1" do compasso: bumbo (graves da bateria isolada, ou da mistura), baixo e trocas de acorde
    env_baixo = None
    if sinal_baixo is not None and np.abs(sinal_baixo).sum() > 0:
        env_baixo, _ = ritmo.envelope_de_ataques(sinal_baixo[: len(sinal)], sr)
        env_baixo = env_baixo[: len(t_grave)]
    trocas = [a.inicio for a in acordes[1:] if a.raiz is not None]
    tempo_forte = ritmo.detectar_tempo_forte(tempos_batidas, grave, t_grave, trocas, env_baixo)
    return Analise(
        duracao=round(duracao, 3),
        bpm=round(bpm, 1),
        compasso="4/4",
        tonalidade=tonalidade,
        batidas=[round(float(t), 3) for t in tempos_batidas],
        acordes=acordes,
        tempo_forte=tempo_forte,
    )


def analisar_arquivo(caminho: str) -> Analise:
    sinal, sr = carregar_audio(caminho)
    return analisar(sinal, sr)
