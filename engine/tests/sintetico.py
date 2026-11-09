"""Gera áudio sintético com acordes conhecidos, para testar o motor sem gravações reais."""

from __future__ import annotations

import numpy as np

SR = 22050
PROGRESSAO_EM = [  # (raiz MIDI, intervalos) — Em, C, G, D
    ("Em", [52, 55, 59, 64, 67]),
    ("C", [48, 52, 55, 60, 64]),
    ("G", [43, 47, 50, 55, 59]),
    ("D", [50, 54, 57, 62, 66]),
]


def _corda(freq: float, dur: float, sr: int = SR) -> np.ndarray:
    t = np.arange(int(dur * sr)) / sr
    onda = sum((0.6 ** k) * np.sin(2 * np.pi * freq * (k + 1) * t) for k in range(5))
    return onda * np.exp(-2.5 * t)


def _bumbo(sr: int = SR) -> np.ndarray:
    t = np.arange(int(0.12 * sr)) / sr
    return np.sin(2 * np.pi * (110 * np.exp(-25 * t)) * t) * np.exp(-30 * t)


def gerar_progressao(bpm: float = 92, repeticoes: int = 2) -> tuple[np.ndarray, list[tuple[str, float, float]]]:
    """Cada acorde dura um compasso de 4/4; batida de bumbo em todo tempo."""
    batida = 60.0 / bpm
    compasso = 4 * batida
    total = len(PROGRESSAO_EM) * repeticoes * compasso + 1.0
    sinal = np.zeros(int(total * SR))
    gabarito = []
    t = 0.5
    for _ in range(repeticoes):
        for nome, midis in PROGRESSAO_EM:
            gabarito.append((nome, t, t + compasso))
            for tempo in range(4):  # violão "batendo" o acorde a cada tempo
                ini = int((t + tempo * batida) * SR)
                for i, m in enumerate(midis):
                    nota = _corda(440 * 2 ** ((m - 69) / 12), batida * 1.2) * 0.18
                    a = ini + i * 80  # leve arpejo, como uma palhetada
                    sinal[a:a + len(nota)] += nota[: len(sinal) - a]
                k = _bumbo()
                sinal[ini:ini + len(k)] += k[: len(sinal) - ini] * 0.8
            t += compasso
    sinal /= np.abs(sinal).max()
    return sinal.astype(np.float32), gabarito


def _nota(midi: float, dur: float, sr: int = SR, decaimento: float = 3.0) -> np.ndarray:
    t = np.arange(int(dur * sr)) / sr
    f = 440 * 2 ** ((midi - 69) / 12)
    onda = sum((0.5 ** k) * np.sin(2 * np.pi * f * (k + 1) * t) for k in range(6))
    ataque = np.minimum(1.0, t / 0.01)
    return onda * ataque * np.exp(-decaimento * t)


def gerar_solo_sobre_acordes(bpm: float = 100, repeticoes: int = 2, volume_solo: float = 0.5, semente: int = 7):
    """Acordes tocados uma vez por compasso (sustentados), baixo na fundamental
    e um solo em colcheias por cima, com notas da escala de Mi menor, como num solo ou dedilhado.

    Retorna (mistura, baixo_isolado, gabarito).
    """
    rng = np.random.default_rng(semente)
    batida = 60.0 / bpm
    compasso = 4 * batida
    total = len(PROGRESSAO_EM) * repeticoes * compasso + 1.0
    mistura = np.zeros(int(total * SR))
    baixo = np.zeros_like(mistura)
    escala = [64, 66, 67, 69, 71, 74, 76, 78, 79, 81]  # Mi menor, região aguda
    gabarito = []
    t = 0.5
    for _ in range(repeticoes):
        for nome, midis in PROGRESSAO_EM:
            gabarito.append((nome, t, t + compasso))
            ini = int(t * SR)
            for m in midis[:4]:  # acorde soando o compasso inteiro, baixinho
                n = _nota(m, compasso, decaimento=0.6) * 0.10
                mistura[ini:ini + len(n)] += n[: len(mistura) - ini]
            b = _nota(midis[0] - 12, compasso, decaimento=0.8) * 0.35
            baixo[ini:ini + len(b)] += b[: len(baixo) - ini]
            for k in range(8):  # solo em colcheias, mais alto que o acorde
                m = int(rng.choice(escala))
                n = _nota(m, batida / 2 * 0.95, decaimento=4.0) * volume_solo
                a = int((t + k * batida / 2) * SR)
                mistura[a:a + len(n)] += n[: len(mistura) - a]
            t += compasso
    mistura += baixo
    escala_max = np.abs(mistura).max()
    return (mistura / escala_max).astype(np.float32), (baixo / escala_max).astype(np.float32), gabarito


def gerar_levada(colcheias_atacadas, bpm: float = 100, compassos: int = 8):
    """Violão tocando sempre a mesma levada: acorde de Em palhetado nas colcheias indicadas
    (0 a 7 dentro do compasso). Retorna (sinal, batidas_reais)."""
    batida = 60.0 / bpm
    total = compassos * 4 * batida + 1.0
    sinal = np.zeros(int(total * SR))
    acorde = [52, 55, 59, 64, 67]
    inicio = 0.5
    for c in range(compassos):
        for k in colcheias_atacadas:
            t = inicio + c * 4 * batida + k * batida / 2
            ini = int(t * SR)
            for i, m in enumerate(acorde):
                n = _nota(m, batida, decaimento=5.0) * 0.2
                n *= np.minimum(1.0, np.linspace(8.0, 0.0, len(n)))  # a nota morre aos poucos, sem clique no fim
                a = ini + i * 60
                sinal[a:a + len(n)] += n[: len(sinal) - a]
    batidas = [inicio + i * batida for i in range(compassos * 4)]
    return (sinal / np.abs(sinal).max()).astype(np.float32), batidas


def gerar_musica_com_bateria(colcheias_atacadas, bpm: float = 100, compassos: int = 16, anacruse: int = 0):
    """Banda simples: violão na levada indicada trocando de acorde a cada compasso
    (Em, C, G, D), bumbo no 1 e no 3, caixa no 2 e no 4.

    Com `anacruse` = n, a gravação começa n tempos antes do primeiro "1" (como uma
    música que entra no fim de um compasso). Retorna (mistura, violao, bateria, uns),
    em que `uns` são os tempos reais de cada "1" do compasso.
    """
    rng = np.random.default_rng(3)
    batida = 60.0 / bpm
    inicio = 0.5 + anacruse * batida  # tempo do primeiro "1"
    total = inicio + compassos * 4 * batida + 1.0
    violao = np.zeros(int(total * SR))
    bateria = np.zeros_like(violao)
    uns = []
    for c in range(-1 if anacruse else 0, compassos):
        t_compasso = inicio + c * 4 * batida
        if c >= 0:
            uns.append(t_compasso)
        _, acorde = PROGRESSAO_EM[c % len(PROGRESSAO_EM)]
        for k in colcheias_atacadas:
            t = t_compasso + k * batida / 2
            if t < 0.5 - 1e-6:
                continue  # antes da gravação começar
            ini = int(t * SR)
            for i, m in enumerate(acorde):
                n = _nota(m, batida, decaimento=5.0) * 0.2
                n *= np.minimum(1.0, np.linspace(8.0, 0.0, len(n)))
                a = ini + i * 60
                violao[a:a + len(n)] += n[: len(violao) - a]
        for tempo in range(4):
            t = t_compasso + tempo * batida
            if t < 0.5 - 1e-6:
                continue
            ini = int(t * SR)
            if tempo % 2 == 0:
                k = _bumbo() * 0.9
            else:
                dur = int(0.08 * SR)
                k = rng.normal(0, 0.35, dur) * np.exp(-np.arange(dur) / SR * 40)
            bateria[ini:ini + len(k)] += k[: len(bateria) - ini]
    escala = max(np.abs(violao).max(), np.abs(bateria).max())
    violao, bateria = violao / escala, bateria / escala
    mistura = 0.6 * violao + bateria
    mistura /= np.abs(mistura).max()
    return mistura.astype(np.float32), violao.astype(np.float32), bateria.astype(np.float32), uns


def gerar_levada_variada(compassos_colcheias, bpm: float = 100, ruido: float = 0.0):
    """Violão cuja levada muda a cada compasso (`compassos_colcheias`: uma lista de
    colcheias atacadas por compasso), opcionalmente com um ruído de fundo constante,
    como o vazamento de uma faixa separada. Retorna (sinal, batidas, golpes_reais)."""
    batida = 60.0 / bpm
    inicio = 0.5
    total = inicio + len(compassos_colcheias) * 4 * batida + 1.0
    sinal = np.zeros(int(total * SR))
    acorde = [52, 55, 59, 64, 67]
    golpes = []
    for c, colcheias in enumerate(compassos_colcheias):
        for k in colcheias:
            t = inicio + c * 4 * batida + k * batida / 2
            golpes.append((t, "baixo" if k % 2 == 0 else "cima"))
            ini = int(t * SR)
            for i, m in enumerate(acorde):
                n = _nota(m, batida, decaimento=5.0) * 0.2
                n *= np.minimum(1.0, np.linspace(8.0, 0.0, len(n)))
                a = ini + i * 60
                sinal[a:a + len(n)] += n[: len(sinal) - a]
    sinal /= np.abs(sinal).max()
    if ruido:
        sinal += np.random.default_rng(7).normal(0, ruido, len(sinal))
    batidas = [inicio + i * batida for i in range(len(compassos_colcheias) * 4 + 1)]
    return sinal.astype(np.float32), batidas, golpes
