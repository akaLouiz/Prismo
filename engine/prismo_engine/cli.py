"""Linha de comando do motor.

Exemplos:
    prismo minha-musica.mp3 --instrumento violao
    prismo ensaio.mp4 --instrumento baixo --sem-letra
    prismo teste.wav --sem-separacao --saida resultados/
"""

from __future__ import annotations

import argparse
import sys

from .pipeline import INSTRUMENTOS, processar


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="prismo", description="Separa a música e gera cifra, tablatura e partitura.")
    p.add_argument("arquivo", help="Áudio (MP3, WAV, M4A...) ou vídeo (MP4, MOV...)")
    p.add_argument("-i", "--instrumento", default="guitarra", choices=sorted(INSTRUMENTOS))
    p.add_argument("-o", "--saida", default=None, help="Pasta dos resultados (padrão: saida/<nome do arquivo>)")
    p.add_argument("--sem-separacao", action="store_true", help="Não separa as faixas (mais rápido, menos preciso)")
    p.add_argument("--sem-letra", action="store_true", help="Não reconhece a letra")
    p.add_argument("--sem-transcricao", action="store_true", help="Só análise e cifra, sem notas")
    p.add_argument("--dispositivo", default=None, help="'cuda' para GPU NVIDIA, 'cpu' para forçar CPU")
    args = p.parse_args(argv)

    resultado = processar(
        args.arquivo,
        instrumento=args.instrumento,
        pasta_saida=args.saida,
        separar=not args.sem_separacao,
        letra=not args.sem_letra,
        transcrever=not args.sem_transcricao,
        dispositivo=args.dispositivo,
    )
    print()
    print(f"Tom: {resultado['tom']['nome']} · {round(resultado['bpm'])} BPM")
    for tipo, caminho in resultado["arquivos"].items():
        print(f"  {tipo}: {caminho}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
