"""Levada: a batida que o violão ou a guitarra realmente toca na música.

O motor acha os ataques de verdade na faixa isolada do instrumento (picos acima do
nível local, ver `ritmo.ataques`) e entrega duas coisas:

- `golpes`: cada ataque, com o tempo e a direção, para o site acender a seta no
  instante em que o violão toca (a levada muda de compasso para compasso);
- `levada`: o padrão de 8 colcheias mais comum, para estudar.

A direção vem da convenção do violão popular: a mão desce no tempo e sobe no
contratempo da menor subdivisão usada. Em levada de colcheias: colcheia par para
baixo, ímpar para cima. Em levada de semicolcheias: semicolcheia par para baixo,
ímpar para cima. O áudio não diz com segurança a direção da palhetada.
"""

from __future__ import annotations

import numpy as np

from .ritmo import ataques, posicao_em_tempos

MINIMO_COMPASSOS = 2
TOLERANCIA = 0.3  # fração da subdivisão: ataque mais longe que isso da grade não conta
SEMICOLCHEIAS = 0.2  # fração de ataques fora das colcheias a partir da qual a levada é de semicolcheias


def _posicoes(sinal: np.ndarray, sr: int, batidas: list[float], tempo_forte: int) -> tuple[np.ndarray, np.ndarray]:
    """Ataques do instrumento e a posição de cada um em semicolcheias desde o primeiro "1"."""
    tempos = ataques(sinal, sr)
    tempos = tempos[tempos >= batidas[0] - 0.1]
    pos = (np.asarray(posicao_em_tempos(tempos, batidas)) - tempo_forte) * 4
    return tempos, pos


def detectar_golpes(sinal: np.ndarray, sr: int, batidas: list[float], tempo_forte: int = 0) -> list[dict]:
    """Cada ataque do violão: [{"t": segundos, "dir": "baixo"|"cima"}], em ordem."""
    batidas = [float(b) for b in batidas]
    if len(batidas) < 2 or np.abs(sinal).sum() == 0:
        return []
    tempos, pos = _posicoes(sinal, sr, batidas, tempo_forte)
    if len(tempos) == 0:
        return []
    semi = np.round(pos).astype(int)
    perto = np.abs(pos - semi) <= TOLERANCIA
    fora_das_colcheias = np.mean(semi[perto] % 2 == 1) if perto.any() else 0.0
    golpes = []
    for t, k in zip(tempos, semi):
        if fora_das_colcheias >= SEMICOLCHEIAS:
            direcao = "baixo" if k % 2 == 0 else "cima"
        else:
            colcheia = int(np.round(k / 2))
            direcao = "baixo" if colcheia % 2 == 0 else "cima"
        golpes.append({"t": round(float(t), 3), "dir": direcao})
    return golpes


def detectar_levada(sinal: np.ndarray, sr: int, batidas: list[float], tempo_forte: int = 0) -> dict | None:
    """Retorna {"padrao": [8 x "baixo"|"cima"|"pausa"], "confianca": 0..1, "compassos": n}.

    `tempo_forte` é o índice, em `batidas`, do primeiro "1" do compasso.
    `None` quando não dá para dizer (poucos compassos, instrumento quase mudo ou sem
    nenhuma colcheia atacada de forma consistente).
    """
    batidas = [float(b) for b in batidas]
    if len(batidas) < 4 * MINIMO_COMPASSOS + 1 or np.abs(sinal).sum() == 0:
        return None
    _, pos = _posicoes(sinal, sr, batidas, tempo_forte)
    colcheias = pos / 2
    alvo = np.round(colcheias).astype(int)
    validos = (np.abs(colcheias - alvo) <= TOLERANCIA) & (alvo >= 0)
    n_compassos = (len(batidas) - 1 - tempo_forte) // 4
    if n_compassos < MINIMO_COMPASSOS:
        return None
    atacado = np.zeros((n_compassos, 8), dtype=bool)
    for c in alvo[validos]:
        if c // 8 < n_compassos:
            atacado[c // 8, c % 8] = True
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
