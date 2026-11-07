"""Tablatura: decide em qual corda e casa cada nota é tocada.

Uma mesma nota pode ser tocada em vários lugares do braço (o Mi da corda Si na
casa 5 é o mesmo da primeira corda solta). O algoritmo testa todas as posições
possíveis e escolhe, com programação dinâmica (Viterbi), a sequência que exige
menos movimento da mão, preferindo cordas soltas e regiões baixas do braço,
como um músico faria.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product

from .models import Nota
from .ritmo import origem_dos_compassos, posicao_em_tempos

# Afinações em MIDI, da corda mais grave para a mais aguda
AFINACOES = {
    "guitarra": [40, 45, 50, 55, 59, 64],  # E A D G B E
    "violao": [40, 45, 50, 55, 59, 64],
    "baixo": [28, 33, 38, 43],  # E A D G
    "guitarra_drop_d": [38, 45, 50, 55, 59, 64],
}

ROTULOS_CORDAS = {
    6: ["E", "A", "D", "G", "B", "e"],
    4: ["E", "A", "D", "G"],
}

JANELA_ACORDE = 0.035  # notas que começam a menos de 35 ms soam juntas


@dataclass
class Posicao:
    corda: int  # 0 = mais grave
    casa: int


@dataclass
class EventoTab:
    inicio: float
    fim: float
    posicoes: list[Posicao]
    midis: list[int]


def _agrupar(notas: list[Nota]) -> list[list[Nota]]:
    grupos: list[list[Nota]] = []
    for n in sorted(notas, key=lambda n: (n.inicio, n.midi)):
        if grupos and n.inicio - grupos[-1][0].inicio <= JANELA_ACORDE:
            grupos[-1].append(n)
        else:
            grupos.append([n])
    return grupos


def _opcoes_nota(midi: int, afinacao: list[int], max_casa: int) -> list[Posicao]:
    return [
        Posicao(c, midi - base)
        for c, base in enumerate(afinacao)
        if 0 <= midi - base <= max_casa
    ]


def _custo_estatico(posicoes: list[Posicao]) -> float:
    """Quão difícil é tocar esta forma isoladamente."""
    presas = [p.casa for p in posicoes if p.casa > 0]
    abertura = (max(presas) - min(presas)) if len(presas) > 1 else 0
    custo = 0.0
    custo += 0.04 * sum(presas)  # regiões altas do braço custam um pouco mais
    custo += 1.5 * max(0, abertura - 3)  # mais de 4 casas de abertura é difícil
    custo += 0.3 * abertura
    if len(posicoes) > 1:  # em acordes, corda solta deixa a forma mais fácil
        custo -= 0.15 * sum(1 for p in posicoes if p.casa == 0)
    return custo


ALCANCE_MAO = 3  # sem mover a mão, os dedos cobrem a casa do indicador + 3


def _janelas(forma: list[Posicao], anteriores: set[int | None]) -> set[int | None]:
    """Posições possíveis da mão (casa do indicador) para tocar esta forma.

    Forma só com cordas soltas não move a mão: herda a posição anterior.
    """
    presas = [p.casa for p in forma if p.casa > 0]
    if not presas:
        return set(anteriores)
    menor, maior = min(presas), max(presas)
    if maior - menor > ALCANCE_MAO:  # abertura grande: indicador na casa mais baixa
        return {menor}
    return set(range(max(1, maior - ALCANCE_MAO), menor + 1))


def _custo_mover(de: int | None, para: int | None) -> float:
    if de is None or para is None or de == para:
        return 0.0
    return 1.0 + 0.5 * abs(de - para)


def _custo_cordas(a: list[Posicao], b: list[Posicao]) -> float:
    """Pequena preferência por continuar nas mesmas cordas (melodias fluídas)."""
    cordas_a = {p.corda for p in a}
    cordas_b = {p.corda for p in b}
    if not cordas_a or not cordas_b:
        return 0.0
    return 0.25 * min(abs(x - y) for x in cordas_a for y in cordas_b)


def _formas_do_grupo(grupo: list[Nota], afinacao: list[int], max_casa: int, limite: int = 60) -> list[list[Posicao]]:
    # Notas que não cabem no instrumento são transpostas por oitava até caber
    menor, maior = afinacao[0], afinacao[-1] + max_casa
    midis = []
    for n in grupo:
        m = n.midi
        while m < menor:
            m += 12
        while m > maior:
            m -= 12
        midis.append(m)
    midis = sorted(set(midis))[: len(afinacao)]

    # Versões do acorde a testar: completo e sem as notas dobradas (mesma nota
    # em outra oitava). Quem toca omite dobras que deixariam a forma difícil.
    conjuntos = [midis]
    for m in midis:
        if any(o != m and o % 12 == m % 12 for o in midis):
            conjuntos.append([x for x in midis if x != m])

    formas = []
    for conjunto in conjuntos:
        opcoes = [_opcoes_nota(m, afinacao, max_casa) for m in conjunto]
        omitidas = len(midis) - len(conjunto)
        for combinacao in product(*opcoes):
            cordas = [p.corda for p in combinacao]
            if len(set(cordas)) == len(cordas):  # uma nota por corda
                formas.append((_custo_estatico(list(combinacao)) + 0.6 * omitidas, list(combinacao)))
    formas.sort(key=lambda x: x[0])
    return [f for _, f in formas[:limite]]


def gerar_tablatura(notas: list[Nota], instrumento: str = "guitarra", max_casa: int = 20) -> list[EventoTab]:
    afinacao = AFINACOES.get(instrumento, AFINACOES["guitarra"])
    grupos = [g for g in _agrupar(notas)]
    candidatos = []
    for g in grupos:
        formas = _formas_do_grupo(g, afinacao, max_casa)
        if formas:
            candidatos.append((g, formas))
    if not candidatos:
        return []

    # Viterbi sobre (forma, posição da mão). Assim o algoritmo decide onde a mão
    # fica olhando a frase inteira, e não só a nota atual.
    camadas: list[list[tuple[int, int | None, float, int]]] = []  # (forma, mão, custo, volta)
    primeiras = candidatos[0][1]
    def custo_base(f: list[Posicao], formas: list[list[Posicao]]) -> float:
        omitidas = max(len(x) for x in formas) - len(f)
        return _custo_estatico(f) + 0.6 * omitidas

    camadas.append([
        (k, mao, custo_base(f, primeiras), -1)
        for k, f in enumerate(primeiras)
        for mao in _janelas(f, {None})
    ])
    for i in range(1, len(candidatos)):
        anteriores = candidatos[i - 1][1]
        maos_anteriores = {estado[1] for estado in camadas[-1]}
        camada = []
        for k, f in enumerate(candidatos[i][1]):
            base = custo_base(f, candidatos[i][1])
            for mao in _janelas(f, maos_anteriores):
                melhor, melhor_j = float("inf"), -1
                for j, (kj, mao_j, custo_j, _) in enumerate(camadas[-1]):
                    if not any(p.casa > 0 for p in f) and mao != mao_j:
                        continue  # corda solta não move a mão
                    total = custo_j + _custo_mover(mao_j, mao) + _custo_cordas(anteriores[kj], f)
                    if total < melhor:
                        melhor, melhor_j = total, j
                if melhor_j >= 0:
                    camada.append((k, mao, melhor + base, melhor_j))
        camadas.append(camada)

    escolha = [0] * len(candidatos)
    j = min(range(len(camadas[-1])), key=lambda x: camadas[-1][x][2])
    for i in range(len(candidatos) - 1, -1, -1):
        k, _, _, volta = camadas[i][j]
        escolha[i] = k
        j = volta

    eventos = []
    for (grupo, formas), k in zip(candidatos, escolha):
        forma = formas[k]
        eventos.append(EventoTab(
            inicio=min(n.inicio for n in grupo),
            fim=max(n.fim for n in grupo),
            posicoes=forma,
            midis=[afinacao[p.corda] + p.casa for p in forma],
        ))
    return eventos


def renderizar_tablatura(
    eventos: list[EventoTab],
    bpm: float,
    instrumento: str = "guitarra",
    tempos_por_compasso: int = 4,
    compassos_por_linha: int = 4,
    divisoes_por_tempo: int = 4,
    inicio_musica: float = 0.0,
    batidas: list[float] | None = None,
    tempo_forte: int = 0,
) -> str:
    """Desenha a tablatura em texto (ASCII), com barras de compasso.

    Cada tempo é dividido em semicolcheias; cada divisão ocupa 3 caracteres,
    o que acomoda casas de dois dígitos. Com `batidas`, as notas seguem os tempos
    reais da gravação e os compassos começam no "1" (`tempo_forte`); sem elas, usa
    uma grade fixa de `bpm` a partir de `inicio_musica`.
    """
    afinacao = AFINACOES.get(instrumento, AFINACOES["guitarra"])
    n_cordas = len(afinacao)
    rotulos = ROTULOS_CORDAS.get(n_cordas, [str(i) for i in range(n_cordas)])
    if not eventos:
        return ""
    seg_por_divisao = 60.0 / bpm / divisoes_por_tempo
    divisoes_por_compasso = tempos_por_compasso * divisoes_por_tempo

    usar_batidas = batidas is not None and len(batidas) >= 2
    origem = origem_dos_compassos(tempo_forte) if usar_batidas else 0

    grade: dict[int, list[Posicao]] = {}
    for ev in eventos:
        if usar_batidas:
            slot = round((posicao_em_tempos(ev.inicio, batidas) - origem) * divisoes_por_tempo)
        else:
            slot = round((ev.inicio - inicio_musica) / seg_por_divisao)
        slot = max(slot, 0)
        while slot in grade:  # dois eventos no mesmo slot: empurra o segundo
            slot += 1
        grade[slot] = ev.posicoes

    total_compassos = max(grade) // divisoes_por_compasso + 1
    largura = 3
    linhas_saida = []
    for inicio_bloco in range(0, total_compassos, compassos_por_linha):
        cordas_txt = [f"{rotulos[c]}|" for c in range(n_cordas)]
        for compasso in range(inicio_bloco, min(inicio_bloco + compassos_por_linha, total_compassos)):
            for d in range(divisoes_por_compasso):
                slot = compasso * divisoes_por_compasso + d
                posicoes = {p.corda: p.casa for p in grade.get(slot, [])}
                for c in range(n_cordas):
                    if c in posicoes:
                        cordas_txt[c] += str(posicoes[c]).ljust(largura, "-")
                    else:
                        cordas_txt[c] += "-" * largura
            for c in range(n_cordas):
                cordas_txt[c] += "|"
        # A corda mais aguda vai em cima, como na tablatura tradicional
        linhas_saida.append("\n".join(reversed(cordas_txt)))
    return "\n\n".join(linhas_saida) + "\n"
