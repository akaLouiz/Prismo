"""Partitura: converte notas detectadas em MusicXML e MIDI.

O MusicXML abre no MuseScore, Sibelius e Finale, e o site renderiza com
OpenSheetMusicDisplay ou Verovio.
"""

from __future__ import annotations

from music21 import clef, key, metadata, meter, note, stream, tempo

from .models import Nota, Tonalidade
from .ritmo import bpm_das_batidas, origem_dos_compassos, posicao_em_tempos

# Instrumentos transpositores: quantos semitons a partitura soa acima do real
TRANSPOSICAO = {
    "sax_alto": 9,      # Mi bemol
    "sax_tenor": 14,    # Si bemol, uma oitava acima
    "trompete": 2,      # Si bemol
    "clarinete": 2,     # Si bemol
}


def linha_melodica(notas: list[Nota]) -> list[Nota]:
    """Reduz notas simultâneas à mais aguda (técnica 'skyline') e corta sobreposições."""
    ordenadas = sorted(notas, key=lambda n: (n.inicio, -n.midi))
    melodia: list[Nota] = []
    for n in ordenadas:
        if melodia and abs(n.inicio - melodia[-1].inicio) < 0.05:
            # Começam juntas: fica a mais aguda
            if n.midi > melodia[-1].midi:
                melodia[-1] = n
            continue
        if melodia and n.inicio < melodia[-1].fim:
            anterior = melodia[-1]
            melodia[-1] = Nota(anterior.inicio, n.inicio, anterior.midi, anterior.intensidade)
        melodia.append(n)
    return [n for n in melodia if n.duracao > 0.04]


def _quantizar(semiminimas: float, grade: float = 0.25) -> float:
    return round(semiminimas / grade) * grade


def criar_partitura(
    notas: list[Nota],
    bpm: float,
    tom: Tonalidade,
    instrumento: str = "voz",
    titulo: str = "Prismo",
    batidas: list[float] | None = None,
    tempo_forte: int = 0,
) -> stream.Score:
    """Com `batidas`, cada nota vai para o tempo real da gravação em que soa, e o
    compasso 1 começa no "1" (ou 4 tempos antes, se houver anacruse; ver
    `origem_dos_compassos`). Sem elas, usa uma grade fixa de `bpm` desde o segundo 0."""
    import numpy as np

    melodia = linha_melodica(notas)
    if batidas is not None and len(batidas) >= 2:
        origem = origem_dos_compassos(tempo_forte)
        bpm = bpm_das_batidas(np.asarray(batidas), bpm)

        def em_semiminimas(t: float) -> float:
            return float(posicao_em_tempos(t, batidas)) - origem
    else:
        def em_semiminimas(t: float) -> float:
            return t * bpm / 60.0
    deslocamento = TRANSPOSICAO.get(instrumento, 0)

    parte = stream.Part()
    parte.append(tempo.MetronomeMark(number=round(bpm)))
    parte.append(meter.TimeSignature("4/4"))
    parte.append(key.Key(_nome_music21(tom), "minor" if tom.modo == "menor" else "major"))
    if instrumento in ("baixo",):
        parte.append(clef.BassClef())
    else:
        parte.append(clef.TrebleClef())

    ultimo_fim = 0.0
    for n in melodia:
        inicio = max(_quantizar(em_semiminimas(n.inicio)), 0.0)
        duracao = max(_quantizar(em_semiminimas(n.fim)) - inicio, 0.25)
        if inicio < ultimo_fim:
            inicio = ultimo_fim
        nota = note.Note(n.midi + deslocamento, quarterLength=duracao)
        parte.insert(inicio, nota)
        ultimo_fim = inicio + duracao

    partitura = stream.Score()
    partitura.metadata = metadata.Metadata(title=titulo)
    partitura.insert(0, parte)
    return partitura.makeNotation()


def _nome_music21(tom: Tonalidade) -> str:
    from .teoria import nome_nota

    return nome_nota(tom.tonica, tom).replace("b", "-")


def exportar(partitura: stream.Score, caminho_base: str) -> dict[str, str]:
    xml = partitura.write("musicxml", fp=caminho_base + ".musicxml")
    mid = partitura.write("midi", fp=caminho_base + ".mid")
    return {"musicxml": str(xml), "midi": str(mid)}
