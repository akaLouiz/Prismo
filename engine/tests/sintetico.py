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
