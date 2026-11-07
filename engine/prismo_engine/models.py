"""Estruturas de dados compartilhadas por todo o motor."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Nota:
    """Uma nota detectada no áudio."""

    inicio: float  # segundos
    fim: float  # segundos
    midi: int  # altura MIDI (60 = Dó central)
    intensidade: float = 1.0

    @property
    def duracao(self) -> float:
        return self.fim - self.inicio


@dataclass
class Acorde:
    """Um trecho da música em que um acorde soa."""

    inicio: float
    fim: float
    raiz: int | None  # 0 = C ... 11 = B; None = sem acorde
    qualidade: str  # "maj", "min", "7", "maj7", "min7", "N"
    confianca: float = 0.0


@dataclass
class Palavra:
    """Uma palavra da letra com seu tempo."""

    inicio: float
    fim: float
    texto: str


@dataclass
class Tonalidade:
    tonica: int  # 0 = C ... 11 = B
    modo: str  # "maior" ou "menor"
    confianca: float = 0.0


@dataclass
class Analise:
    """Resultado da análise musical de uma faixa."""

    duracao: float
    bpm: float
    compasso: str
    tonalidade: Tonalidade
    batidas: list[float] = field(default_factory=list)
    acordes: list[Acorde] = field(default_factory=list)
    tempo_forte: int = 0  # índice, em `batidas`, do primeiro tempo "1" do compasso

    def para_dict(self) -> dict:
        return asdict(self)
