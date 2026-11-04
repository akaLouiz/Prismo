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
