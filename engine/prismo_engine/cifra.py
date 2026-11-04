"""Cifra no padrão brasileiro: acordes alinhados sobre a sílaba da letra.

Com letra (palavras com tempo, vindas do reconhecimento de fala na voz
isolada), cada acorde é posicionado sobre a palavra em que ele entra.
Sem letra, a cifra sai por compassos: | Em . . . | C . . . |
"""

from __future__ import annotations

from .models import Acorde, Palavra, Tonalidade
from .teoria import nome_acorde, nome_tonalidade, sugerir_capotraste

PAUSA_NOVA_LINHA = 0.9  # segundos de silêncio que quebram a linha da letra
MAX_PALAVRAS_LINHA = 9
ACORDE_MINIMO = 0.35  # trechos mais curtos que isso são ruído da detecção


def limpar_acordes(acordes: list[Acorde]) -> list[Acorde]:
    """Remove trechos curtos demais e junta vizinhos iguais."""
    limpos: list[Acorde] = []
    for a in acordes:
        if a.fim - a.inicio < ACORDE_MINIMO and limpos:
            limpos[-1].fim = a.fim
            continue
        if limpos and (limpos[-1].raiz, limpos[-1].qualidade) == (a.raiz, a.qualidade):
            limpos[-1].fim = a.fim
        else:
            limpos.append(Acorde(a.inicio, a.fim, a.raiz, a.qualidade, a.confianca))
    return limpos


def _linhas_da_letra(palavras: list[Palavra]) -> list[list[Palavra]]:
    linhas: list[list[Palavra]] = []
    for p in palavras:
        nova = (
            not linhas
            or p.inicio - linhas[-1][-1].fim > PAUSA_NOVA_LINHA
            or len(linhas[-1]) >= MAX_PALAVRAS_LINHA
        )
        if nova:
            linhas.append([p])
        else:
            linhas[-1].append(p)
    return linhas


def _cifra_com_letra(acordes: list[Acorde], palavras: list[Palavra], tom: Tonalidade) -> list[str]:
    saida: list[str] = []
    linhas = _linhas_da_letra(palavras)
    usados: set[int] = set()
    for i, linha in enumerate(linhas):
        inicio_linha = linha[0].inicio
        fim_linha = linhas[i + 1][0].inicio if i + 1 < len(linhas) else float("inf")
        texto = ""
        colunas = []
        for p in linha:
            colunas.append(len(texto))
            texto += p.texto.strip() + " "
        texto = texto.rstrip()

        acordes_linha = ""
        for idx, a in enumerate(acordes):
            if idx in usados or a.raiz is None:
                continue
            # Acorde que entra antes da linha começar vale para a primeira palavra
            if a.inicio >= fim_linha:
                break
            if a.fim <= inicio_linha:
                continue
            alvo = 0
            for k, p in enumerate(linha):
                if p.inicio <= a.inicio + 0.15:
                    alvo = k
            coluna = colunas[alvo]
            # Se a palavra já foi ocupada por outro acorde, avança até ter espaço
            coluna = max(coluna, len(acordes_linha) + (1 if acordes_linha else 0))
            acordes_linha = acordes_linha.ljust(coluna) + nome_acorde(a, tom)
            usados.add(idx)
        saida.append(acordes_linha.rstrip())
        saida.append(texto)
        saida.append("")
    return saida


def _cifra_por_compassos(
    acordes: list[Acorde],
    tom: Tonalidade,
    bpm: float,
    inicio: float | None = None,
    compassos_por_linha: int = 4,
) -> list[str]:
    duracao_compasso = 4 * 60.0 / bpm
    tocados = [a for a in acordes if a.raiz is not None]
    if not tocados:
        return []
    fim = tocados[-1].fim
    compassos = []
    # A grade de compassos começa na primeira batida (ou no primeiro acorde)
    t = inicio if inicio is not None else tocados[0].inicio
    minimo = 0.3 * duracao_compasso  # acorde precisa ocupar ~1 tempo do compasso
    while t < fim - 0.05:
        no_compasso = [
            a for a in tocados
            if min(a.fim, t + duracao_compasso) - max(a.inicio, t) >= minimo
        ]
        nomes = []
        for a in no_compasso:
            n = nome_acorde(a, tom)
            if not nomes or nomes[-1] != n:
                nomes.append(n)
        compassos.append("  ".join(nomes) if nomes else "%")
        t += duracao_compasso
    while compassos and compassos[-1] == "%":  # silêncio no fim da gravação
        compassos.pop()
    largura = max(len(c) for c in compassos) + 2
    linhas = []
    for i in range(0, len(compassos), compassos_por_linha):
        bloco = compassos[i:i + compassos_por_linha]
        linhas.append("| " + "| ".join(c.ljust(largura) for c in bloco) + "|")
    return linhas


def gerar_cifra(
    acordes: list[Acorde],
    tom: Tonalidade,
    bpm: float,
    palavras: list[Palavra] | None = None,
    titulo: str = "",
    inicio_compassos: float | None = None,
) -> str:
    acordes = limpar_acordes(acordes)
    capo = sugerir_capotraste(acordes)
    cabecalho = []
    if titulo:
        cabecalho.append(titulo)
    cabecalho.append(f"Tom: {nome_tonalidade(tom)} ({nome_tonalidade(tom, em_portugues=True)})")
    cabecalho.append(f"Andamento: {round(bpm)} BPM")
    if capo["casa"]:
        cabecalho.append(f"Sugestão: capotraste na {capo['casa']}ª casa")
    nomes_unicos = []
    for a in acordes:
        n = nome_acorde(a, tom)
        if a.raiz is not None and n not in nomes_unicos:
            nomes_unicos.append(n)
    cabecalho.append("Acordes: " + "  ".join(nomes_unicos))

    corpo = (
        _cifra_com_letra(acordes, palavras, tom)
        if palavras
        else _cifra_por_compassos(acordes, tom, bpm, inicio_compassos)
    )
    return "\n".join(cabecalho) + "\n\n" + "\n".join(corpo).rstrip() + "\n"
