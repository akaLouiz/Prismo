"""Levada: o padrão de batida que o violão ou a guitarra realmente toca na música.

Em cada compasso (4 tempos, a partir das batidas detectadas), o motor olha as 8
colcheias e marca onde há ataque de palhetada na faixa isolada do instrumento.
As colcheias atacadas na maioria dos compassos formam a levada da música.

A direção vem da convenção do violão popular: ataque no tempo é para baixo, no
contratempo é para cima. O áudio não diz com segurança a direção da palhetada.
"""

from __future__ import annotations

import numpy as np
import librosa

SALTO = 256
JANELA = 0.06  # segundos em volta de cada colcheia em que um ataque conta
MINIMO_COMPASSOS = 2


def detectar_levada(sinal: np.ndarray, sr: int, batidas: list[float]) -> dict | None:
    """Retorna {"padrao": [8 x "baixo"|"cima"|"pausa"], "confianca": 0..1, "compassos": n}.

    `None` quando não dá para dizer (poucos compassos, instrumento quase mudo ou sem
    nenhuma colcheia atacada de forma consistente).
    """
    batidas = [float(b) for b in batidas]
    if len(batidas) < 4 * MINIMO_COMPASSOS + 1 or np.abs(sinal).sum() == 0:
        return None
    envelope = librosa.onset.onset_strength(y=sinal, sr=sr, hop_length=SALTO)
    if envelope.max() <= 0:
        return None
    tempos = librosa.frames_to_time(np.arange(len(envelope)), sr=sr, hop_length=SALTO)
    referencia = np.percentile(envelope, 95) or envelope.max()

    def ataque(t: float) -> float:
        sel = (tempos >= t - JANELA) & (tempos <= t + JANELA)
        return float(envelope[sel].max() / referencia) if sel.any() else 0.0

    compassos = []
    for inicio in range(0, len(batidas) - 4, 4):
        tempos_compasso = batidas[inicio:inicio + 5]
        forcas = []
        for k in range(4):
            a, b = tempos_compasso[k], tempos_compasso[k + 1]
            forcas.append(ataque(a))
            forcas.append(ataque((a + b) / 2))
        compassos.append(forcas)
    if len(compassos) < MINIMO_COMPASSOS:
        return None

    forcas = np.array(compassos)  # compassos x 8
    atacado = forcas >= 0.35
    # Compassos quase mudos (pausa, trecho só de voz) não votam
    ativos = atacado.sum(axis=1) >= 2
    if ativos.sum() < MINIMO_COMPASSOS:
        return None
    frequencia = atacado[ativos].mean(axis=0)  # em quantos compassos cada colcheia é atacada
    marcado = frequencia >= 0.5
    if not marcado.any():
        return None
    padrao = [("baixo" if i % 2 == 0 else "cima") if marcado[i] else "pausa" for i in range(8)]
    # Confiança: o quanto os compassos concordam com o padrão escolhido
    concordancia = float(np.mean(np.where(marcado, frequencia, 1 - frequencia)))
    return {"padrao": padrao, "confianca": round(concordancia, 3), "compassos": int(ativos.sum())}
