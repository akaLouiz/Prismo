"""Teoria musical: nomes de notas, cifra no padrão brasileiro e transposição."""

from __future__ import annotations

import re

from .models import Acorde, Tonalidade

SUSTENIDOS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
BEMOIS = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]

# Tonalidades que se escrevem com bemóis (tônica, modo)
_TONS_COM_BEMOL = {
    (5, "maior"), (10, "maior"), (3, "maior"), (8, "maior"), (1, "maior"), (6, "maior"),
    (2, "menor"), (7, "menor"), (0, "menor"), (5, "menor"), (10, "menor"), (3, "menor"),
}

# Sufixo de cada qualidade no padrão de cifra brasileiro
SUFIXOS = {
    "maj": "",
    "min": "m",
    "7": "7",
    "maj7": "7M",
    "min7": "m7",
    "dim": "°",
    "N": "",
}

NOMES_EM_PT = {
    "C": "Dó", "C#": "Dó sustenido", "Db": "Ré bemol", "D": "Ré", "D#": "Ré sustenido",
    "Eb": "Mi bemol", "E": "Mi", "F": "Fá", "F#": "Fá sustenido", "Gb": "Sol bemol",
    "G": "Sol", "G#": "Sol sustenido", "Ab": "Lá bemol", "A": "Lá", "A#": "Lá sustenido",
    "Bb": "Si bemol", "B": "Si",
}


def usa_bemol(tom: Tonalidade | None) -> bool:
    return tom is not None and (tom.tonica, tom.modo) in _TONS_COM_BEMOL


def nome_nota(classe: int, tom: Tonalidade | None = None) -> str:
    tabela = BEMOIS if usa_bemol(tom) else SUSTENIDOS
    return tabela[classe % 12]


def nome_acorde(acorde: Acorde, tom: Tonalidade | None = None) -> str:
    """Escreve o acorde como na cifra brasileira: Em, C7M, Am7, F#°."""
    if acorde.raiz is None or acorde.qualidade == "N":
        return "N.C."
    return nome_nota(acorde.raiz, tom) + SUFIXOS.get(acorde.qualidade, "")


def nome_tonalidade(tom: Tonalidade, em_portugues: bool = False) -> str:
    nota = nome_nota(tom.tonica, tom)
    if em_portugues:
        return f"{NOMES_EM_PT[nota]} {tom.modo}"
    return nota + ("m" if tom.modo == "menor" else "")


def transpor_tom(tom: Tonalidade, semitons: int) -> Tonalidade:
    return Tonalidade((tom.tonica + semitons) % 12, tom.modo, tom.confianca)


def transpor_acordes(acordes: list[Acorde], semitons: int) -> list[Acorde]:
    return [
        Acorde(a.inicio, a.fim, None if a.raiz is None else (a.raiz + semitons) % 12, a.qualidade, a.confianca)
        for a in acordes
    ]


_RE_CIFRA = re.compile(r"\b([A-G])([#b]?)")


def transpor_texto_cifra(texto: str, semitons: int, bemol: bool = False) -> str:
    """Transpõe nomes de acordes dentro de um texto (ex.: 'D/F#' vira 'E/G#')."""
    tabela = BEMOIS if bemol else SUSTENIDOS

    def troca(m: re.Match) -> str:
        nome = m.group(1) + m.group(2)
        idx = SUSTENIDOS.index(nome) if nome in SUSTENIDOS else BEMOIS.index(nome)
        return tabela[(idx + semitons) % 12]

    return _RE_CIFRA.sub(troca, texto)


# Acordes que ficam em "formato aberto" no violão (fáceis, sem pestana)
_FORMATOS_ABERTOS = {
    (0, "maj"), (2, "maj"), (4, "maj"), (7, "maj"), (9, "maj"),
    (2, "min"), (4, "min"), (9, "min"),
    (0, "7"), (2, "7"), (4, "7"), (7, "7"), (9, "7"), (11, "7"),
    (0, "maj7"), (5, "maj7"), (2, "maj7"),
    (9, "min7"), (4, "min7"), (2, "min7"),
}


def sugerir_capotraste(acordes: list[Acorde], max_casa: int = 5, ganho_minimo: float = 0.2) -> dict:
    """Escolhe a casa do capotraste que deixa mais acordes em formato aberto.

    Com o capo na casa N, toca-se o formato do acorde N semitons abaixo. Capo alto no
    braço não é prático: nunca passa de `max_casa`, cada casa custa um pouco, e só há
    sugestão quando o capo deixa pelo menos 20% mais acordes abertos do que sem ele.
    A mesma regra está no site (suggestCapo em src/lib/music/index.ts).
    Retorna a casa sugerida e quantos acordes (ponderados pela duração) ficam abertos.
    """
    validos = [a for a in acordes if a.raiz is not None and a.qualidade != "N"]
    if not validos:
        return {"casa": 0, "aproveitamento": 0.0}
    total = sum(a.fim - a.inicio for a in validos) or 1.0

    def taxa(casa: int) -> float:
        abertos = sum(a.fim - a.inicio for a in validos if ((a.raiz - casa) % 12, a.qualidade) in _FORMATOS_ABERTOS)
        return abertos / total

    sem_capo = taxa(0)
    melhor = (0, sem_capo)
    for casa in range(1, max_casa + 1):
        t = taxa(casa)
        if t - sem_capo >= ganho_minimo and t - 0.02 * casa > melhor[1] - 0.02 * melhor[0]:
            melhor = (casa, t)
    return {"casa": melhor[0], "aproveitamento": round(melhor[1], 3)}
