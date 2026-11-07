import numpy as np
import pytest

from prismo_engine.analise import analisar
from prismo_engine.cifra import gerar_cifra
from prismo_engine.models import Acorde, Nota, Palavra, Tonalidade
from prismo_engine.partitura import criar_partitura, linha_melodica
from prismo_engine.tablatura import gerar_tablatura, renderizar_tablatura
from prismo_engine.teoria import (
    nome_acorde,
    nome_tonalidade,
    sugerir_capotraste,
    transpor_acordes,
    transpor_texto_cifra,
)

from sintetico import SR, gerar_progressao

EM_MENOR = Tonalidade(4, "menor")


# ---------- Análise com áudio sintético ----------

@pytest.fixture(scope="module")
def analise_sintetica():
    sinal, gabarito = gerar_progressao(bpm=92, repeticoes=2)
    return analisar(sinal, SR), gabarito


def test_bpm(analise_sintetica):
    analise, _ = analise_sintetica
    assert abs(analise.bpm - 92) < 4 or abs(analise.bpm - 184) < 8


def test_tonalidade(analise_sintetica):
    analise, _ = analise_sintetica
    # Em menor e Sol maior são relativas (mesmas notas); aceitamos as duas
    assert nome_tonalidade(analise.tonalidade) in {"Em", "G"}


def test_acordes_batem_com_o_gabarito(analise_sintetica):
    analise, gabarito = analise_sintetica
    acertos = 0
    for nome, ini, fim in gabarito:
        meio = (ini + fim) / 2
        detectado = next(a for a in analise.acordes if a.inicio <= meio < a.fim)
        acertos += nome_acorde(detectado) == nome
    assert acertos / len(gabarito) >= 0.75, [nome_acorde(a) for a in analise.acordes]


# ---------- Teoria ----------

def test_cifra_no_padrao_brasileiro():
    assert nome_acorde(Acorde(0, 1, 0, "maj7")) == "C7M"
    assert nome_acorde(Acorde(0, 1, 9, "min7")) == "Am7"
    assert nome_acorde(Acorde(0, 1, 10, "maj"), Tonalidade(5, "maior")) == "Bb"
    assert nome_acorde(Acorde(0, 1, 10, "maj"), Tonalidade(4, "menor")) == "A#"
    assert nome_tonalidade(EM_MENOR, em_portugues=True) == "Mi menor"


def test_transposicao():
    acordes = transpor_acordes([Acorde(0, 1, 4, "min")], 2)
    assert nome_acorde(acordes[0]) == "F#m"
    assert transpor_texto_cifra("Em   D/F#  C7M", 2) == "F#m   E/G#  D7M"


def test_capotraste():
    # F#m D A E com capo 2 vira Em C G D, tudo aberto
    acordes = [Acorde(i, i + 1, r, q) for i, (r, q) in enumerate([(6, "min"), (2, "maj"), (9, "maj"), (4, "maj")])]
    assert sugerir_capotraste(acordes)["casa"] == 2
    # Já aberto: sem capo
    acordes = [Acorde(i, i + 1, r, q) for i, (r, q) in enumerate([(4, "min"), (0, "maj"), (7, "maj"), (2, "maj")])]
    assert sugerir_capotraste(acordes)["casa"] == 0


# ---------- Tablatura ----------

def test_acorde_em_vira_formato_aberto():
    notas = [Nota(0.0, 1.0, m) for m in [40, 47, 52, 55, 59, 64]]
    ev = gerar_tablatura(notas, "guitarra")[0]
    casas = {p.corda: p.casa for p in ev.posicoes}
    assert casas == {0: 0, 1: 2, 2: 2, 3: 0, 4: 0, 5: 0}


def test_melodia_fica_numa_regiao_do_braco():
    # Pentatônica de Lá menor, a "caixa" clássica da casa 5 (A2 até C5)
    midis = [45, 48, 50, 52, 55, 57, 60, 62, 64, 67, 69, 72]
    notas = [Nota(i * 0.25, i * 0.25 + 0.2, m) for i, m in enumerate(midis)]
    eventos = gerar_tablatura(notas, "guitarra")
    casas = [p.casa for e in eventos for p in e.posicoes]
    assert casas == [5, 8, 5, 7, 5, 7, 5, 7, 5, 8, 5, 8]


def test_baixo_usa_quatro_cordas():
    notas = [Nota(i * 0.5, i * 0.5 + 0.4, m) for i, m in enumerate([28, 31, 33, 35, 36])]
    eventos = gerar_tablatura(notas, "baixo")
    assert all(p.corda < 4 for e in eventos for p in e.posicoes)
    texto = renderizar_tablatura(eventos, 120, "baixo")
    assert texto.splitlines()[0].startswith("G|")
    assert len(texto.splitlines()[0]) == len(texto.splitlines()[3])


def test_nota_fora_do_alcance_e_ajustada_por_oitava():
    eventos = gerar_tablatura([Nota(0, 1, 30)], "guitarra")
    assert eventos and eventos[0].midis[0] == 42


# ---------- Cifra ----------

def test_cifra_com_letra_alinha_acorde_na_palavra():
    palavras = [Palavra(0.0, 0.4, "Toca"), Palavra(0.5, 0.8, "de"), Palavra(0.9, 1.3, "novo"),
                Palavra(1.4, 1.8, "deixa"), Palavra(1.9, 2.2, "o"), Palavra(2.3, 2.8, "som")]
    acordes = [Acorde(0.0, 1.4, 4, "min"), Acorde(1.4, 3.0, 0, "maj")]
    texto = gerar_cifra(acordes, EM_MENOR, 92, palavras)
    linhas = texto.splitlines()
    i = linhas.index("Toca de novo deixa o som")
    acima = linhas[i - 1]
    assert acima.startswith("Em")
    assert acima.index("C") == linhas[i].index("deixa")


def test_cifra_sem_letra_por_compassos():
    compasso = 4 * 60 / 120
    acordes = [Acorde(i * compasso, (i + 1) * compasso, r, q) for i, (r, q) in enumerate([(4, "min"), (0, "maj"), (7, "maj"), (2, "maj")])]
    texto = gerar_cifra(acordes, EM_MENOR, 120)
    assert "Tom: Em (Mi menor)" in texto
    assert "| Em" in texto and "| D" in texto


# ---------- Partitura ----------

def test_linha_melodica_remove_sobreposicao():
    notas = [Nota(0, 1, 60), Nota(0, 1, 64), Nota(0.5, 1.5, 67)]
    mel = linha_melodica(notas)
    assert [n.midi for n in mel] == [64, 67]
    assert mel[0].fim <= mel[1].inicio + 1e-9


def test_partitura_gera_musicxml(tmp_path):
    notas = [Nota(i * 0.5, i * 0.5 + 0.45, m) for i, m in enumerate([64, 66, 67, 69, 71])]
    partitura = criar_partitura(notas, 120, EM_MENOR, "voz", titulo="teste")
    caminho = partitura.write("musicxml", fp=str(tmp_path / "t.musicxml"))
    xml = open(caminho, encoding="utf-8").read()
    assert "<fifths>1</fifths>" in xml  # Mi menor tem um sustenido
    assert xml.count("<note") >= 5


# ---------- Limpeza da transcrição ----------

def test_remove_harmonico_fantasma():
    from prismo_engine.ia import remover_harmonicos

    sol = Nota(0.5, 1.2, 55, 0.65)
    fantasma = Nota(0.78, 1.1, 83, 0.34)  # 5º harmônico do Sol, começou depois
    oitava = Nota(0.5, 1.2, 67, 0.6)  # oitava tocada de verdade: fica
    restantes = remover_harmonicos([sol, fantasma, oitava])
    assert [n.midi for n in restantes] == [55, 67]


def test_cifra_ignora_silencio_no_fim():
    compasso = 2.0
    acordes = [Acorde(0, compasso, 4, "min"), Acorde(compasso, 3 * compasso, None, "N")]
    texto = gerar_cifra(acordes, EM_MENOR, 120)
    assert "%" not in texto


# ---------------------------------------------------------------- solos e dedilhados

def test_baixo_isolado_mantem_acordes_sob_solo():
    """Solo alto por cima de acordes: com a faixa do baixo, os acordes continuam certos."""
    from sintetico import gerar_solo_sobre_acordes
    from prismo_engine.cifra import limpar_acordes

    def acertos(analise, gabarito):
        acs = limpar_acordes(analise.acordes)
        ok = 0
        for nome, ini, fim in gabarito:
            meio = (ini + fim) / 2
            d = next((a for a in acs if a.inicio <= meio < a.fim), None)
            ok += d is not None and nome_acorde(d) == nome
        return ok / len(gabarito)

    mix, baixo, gab = gerar_solo_sobre_acordes(volume_solo=0.8)
    com_baixo = acertos(analisar(mix, SR, sinal_baixo=baixo), gab)
    sem_baixo = acertos(analisar(mix, SR), gab)
    assert com_baixo >= 0.75
    assert com_baixo > sem_baixo


def test_capotraste_nunca_alto_no_braco():
    nomes = [(1, "min7"), (9, "maj7"), (4, "maj"), (11, "min"), (9, "min")]  # C#m7 A7M E Bm Am
    acordes = [Acorde(i, i + 1, r, q) for i, (r, q) in enumerate(nomes)]
    assert sugerir_capotraste(acordes)["casa"] <= 5


# ---------------------------------------------------------------- levada

@pytest.mark.parametrize("nome,colcheias,esperado", [
    ("pop/rock", [0, 1, 3, 4, 5, 6], ["baixo", "cima", "pausa", "cima", "baixo", "cima", "baixo", "pausa"]),
    ("semínimas", [0, 2, 4, 6], ["baixo", "pausa", "baixo", "pausa", "baixo", "pausa", "baixo", "pausa"]),
    ("reggae", [1, 3, 5, 7], ["pausa", "cima", "pausa", "cima", "pausa", "cima", "pausa", "cima"]),
])
def test_detecta_a_levada_tocada(nome, colcheias, esperado):
    from sintetico import gerar_levada
    from prismo_engine.levada import detectar_levada

    sinal, batidas = gerar_levada(colcheias)
    levada = detectar_levada(sinal, SR, batidas)
    assert levada is not None, nome
    assert levada["padrao"] == esperado, nome
    assert levada["confianca"] > 0.8


def test_levada_com_batidas_detectadas_pelo_motor():
    """O mesmo, usando as batidas que o próprio motor detecta (como no uso real)."""
    from sintetico import gerar_levada
    from prismo_engine.levada import detectar_levada

    sinal, _ = gerar_levada([0, 2, 4, 6], bpm=100)
    batidas = analisar(sinal, SR).batidas
    levada = detectar_levada(sinal, SR, batidas)
    assert levada is not None
    atacadas = [i for i, s in enumerate(levada["padrao"]) if s != "pausa"]
    # Batidas detectadas podem começar meio compasso deslocadas; o que importa é atacar 1 a cada 2 colcheias
    assert atacadas in ([0, 2, 4, 6], [1, 3, 5, 7])


def test_sem_levada_em_silencio():
    from prismo_engine.levada import detectar_levada
    import numpy as np

    assert detectar_levada(np.zeros(SR * 10, dtype=np.float32), SR, [i * 0.5 for i in range(20)]) is None
    assert detectar_levada(np.ones(SR, dtype=np.float32), SR, [0.0, 0.5]) is None


# ---------------------------------------------------------------- ritmo: andamento, "1" e grade real

@pytest.mark.parametrize("bpm", [80, 100, 128, 140])
@pytest.mark.parametrize("anacruse", [0, 1, 3])
def test_acha_andamento_e_o_um_do_compasso(bpm, anacruse):
    """Música com bateria: o motor não pode pegar metade do andamento (erro comum
    acima de ~110 BPM, preso só na caixa) nem achar o "1" no tempo errado."""
    from sintetico import gerar_musica_com_bateria
    from prismo_engine.levada import detectar_levada

    mistura, violao, _, uns = gerar_musica_com_bateria([0, 1, 3, 4, 5, 6], bpm=bpm, anacruse=anacruse)
    a = analisar(mistura, SR)
    assert abs(a.bpm - bpm) < 1.5
    um = a.batidas[a.tempo_forte]
    assert min(abs(um - u) for u in uns) < 0.06, (um, uns[:2])
    # Os tempos antes do primeiro "1" (anacruse) não podem sumir
    assert a.batidas[0] < uns[0] - (anacruse - 0.5) * 60 / bpm if anacruse else True
    levada = detectar_levada(violao, SR, a.batidas, a.tempo_forte)
    assert levada["padrao"] == ["baixo", "cima", "pausa", "cima", "baixo", "cima", "baixo", "pausa"]


def test_um_do_compasso_com_bateria_isolada():
    from sintetico import gerar_musica_com_bateria

    mistura, _, bateria, uns = gerar_musica_com_bateria([0, 2, 4, 6], bpm=92, anacruse=2)
    a = analisar(mistura, SR, sinal_bateria=bateria)
    assert min(abs(a.batidas[a.tempo_forte] - u) for u in uns) < 0.06


def test_posicao_em_tempos_segue_as_batidas_reais():
    from prismo_engine.ritmo import posicao_em_tempos

    batidas = [1.0, 1.5, 2.1, 2.6]  # andamento oscilando, como numa gravação ao vivo
    assert posicao_em_tempos(1.0, batidas) == 0
    assert posicao_em_tempos(1.8, batidas) == pytest.approx(1.5)
    assert posicao_em_tempos(0.75, batidas) == pytest.approx(-0.5)  # antes: intervalo da borda
    assert posicao_em_tempos(3.1, batidas) == pytest.approx(4.0)


def test_tablatura_e_partitura_seguem_as_batidas_e_o_um():
    """Andamento que acelera: com grade fixa as notas iam escorregando de tempo."""
    from prismo_engine.partitura import criar_partitura

    batidas, t = [], 0.5
    for i in range(24):
        batidas.append(t)
        t += 0.6 - i * 0.01  # 100 BPM acelerando
    # Anacruse de 1 tempo: o "1" é a batida de índice 1. Uma nota em cada tempo forte.
    notas = [Nota(batidas[i], batidas[i] + 0.2, 64) for i in range(1, 24, 4)]
    tab = renderizar_tablatura(gerar_tablatura(notas), 100, batidas=batidas, tempo_forte=1)
    compassos = [c for linha in tab.split("\n\n") for c in linha.split("\n")[0].split("|")[1:-1]]
    # 1º compasso: anacruse (3 tempos de pausa e o 4º tempo vazio); depois, nota no 1 de cada compasso
    assert all(c.startswith("0") for c in compassos[1:6]), compassos
    partitura = criar_partitura(notas, 100, EM_MENOR, "guitarra", batidas=batidas, tempo_forte=1)
    inicios = [float(n.getOffsetInHierarchy(partitura)) for n in partitura.recurse().notes]
    assert inicios[:6] == [4.0, 8.0, 12.0, 16.0, 20.0, 24.0]


def test_cifra_por_compassos_segue_as_batidas():
    batidas = [0.5 + 0.5 * i for i in range(17)]
    acordes = [Acorde(1.0, 3.0, 4, "min"), Acorde(3.0, 5.0, 0, "maj"), Acorde(5.0, 9.0, 7, "maj")]
    cifra = gerar_cifra(acordes, EM_MENOR, 120, batidas=batidas, tempo_forte=1)
    linha = [l for l in cifra.splitlines() if l.startswith("|")][0]
    assert [c.strip() for c in linha.strip("|").split("|")][:4] == ["%", "Em", "C", "G"]
