"""Fila para servidores sem estado (como o Modal).

A API recebe o pedido num servidor pequeno, sem GPU, e dispara o processamento
de cada música numa máquina com GPU, que liga e desliga sozinha. O estado de
cada música fica num armazenamento compartilhado (no Modal, um `modal.Dict`),
para o /status e para evitar processar a mesma música duas vezes.
"""

from __future__ import annotations

import time
from collections.abc import Callable, MutableMapping

from .api import Config, Fila, PedidoProcessamento, Trabalho

# Depois desse tempo sem notícias, uma música "processando" é considerada perdida
# e pode ser enviada de novo (ex.: a máquina caiu no meio).
PRAZO_TRABALHO = 30 * 60


def _para_trabalho(dados: dict) -> Trabalho:
    t = Trabalho(PedidoProcessamento(**dados["pedido"]))
    t.status = dados.get("status", "na_fila")
    t.etapa = dados.get("etapa")
    t.erro = dados.get("erro")
    t.criado_em = dados.get("criado_em", time.time())
    t.concluido_em = dados.get("concluido_em")
    return t


def _para_dados(t: Trabalho, atualizado_em: float | None = None) -> dict:
    return {
        "pedido": t.pedido.model_dump(),
        "status": t.status,
        "etapa": t.etapa,
        "erro": t.erro,
        "criado_em": t.criado_em,
        "concluido_em": t.concluido_em,
        "atualizado_em": atualizado_em or time.time(),
    }


class FilaRemota(Fila):
    """Fila usada pela API: guarda o estado e dispara o processamento remoto."""

    def __init__(self, config: Config, estado: MutableMapping, disparar: Callable[[dict], None]):
        super().__init__(config)
        self.estado = estado
        self.disparar = disparar

    def iniciar(self) -> None:  # não há trabalhadores locais
        pass

    def adicionar(self, pedido: PedidoProcessamento) -> tuple[Trabalho, bool]:
        atual = self.estado.get(pedido.song_id)
        if atual and atual["status"] in ("na_fila", "processando"):
            if time.time() - atual.get("atualizado_em", 0) < PRAZO_TRABALHO:
                return _para_trabalho(atual), False
        trabalho = Trabalho(pedido)
        self.estado[pedido.song_id] = _para_dados(trabalho)
        self.disparar(pedido.model_dump())
        return trabalho, True

    def obter(self, song_id: str) -> Trabalho | None:
        dados = self.estado.get(song_id)
        return _para_trabalho(dados) if dados else None

    def posicao(self, song_id: str) -> int:
        return 0

    @property
    def tamanho(self) -> int:
        return 0


class ExecutorRemoto(Fila):
    """Roda uma música na máquina com GPU e mantém o estado compartilhado em dia."""

    def __init__(self, config: Config, estado: MutableMapping):
        super().__init__(config)
        self.estado = estado

    def executar(self, dados_pedido: dict) -> dict:
        trabalho = Trabalho(PedidoProcessamento(**dados_pedido))
        self._trabalho_atual = trabalho
        self._executar_trabalho(trabalho)
        self.estado[trabalho.pedido.song_id] = _para_dados(trabalho)
        return trabalho.resumo()

    def _chamar_callback(self, pedido: PedidoProcessamento, corpo: dict, tentativas: int = 1) -> None:
        trabalho = getattr(self, "_trabalho_atual", None)
        if trabalho is not None:
            self.estado[pedido.song_id] = _para_dados(trabalho)
        super()._chamar_callback(pedido, corpo, tentativas)
