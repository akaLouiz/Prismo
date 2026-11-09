"""Ritmo: deixa a grade de tempos do motor presa à música de verdade.

O rastreador de batidas do librosa acha bem o pulso, mas erra três coisas que
desencontram a batida, a tablatura e a partitura da música:

1. Andamento pela metade: numa música a 128 BPM ele pode marcar só 1 tempo a cada 2.
2. Bordas: costuma ignorar os primeiros (e os últimos) tempos da gravação.
3. O "1" do compasso: ele não sabe qual tempo é o primeiro do compasso.

Este módulo corrige os três e oferece `posicao_em_tempos`, que converte segundos
em tempos da música seguindo a lista real de batidas (e não um BPM fixo, que vai
se afastando da gravação com o passar dos compassos).
"""

from __future__ import annotations

import numpy as np
import librosa

SALTO = 512
JANELA = 0.05  # segundos em volta do tempo em que se procura o ataque

# Andamento pela metade: se no meio de cada tempo há ataques quase tão fortes quanto
# nos tempos, a música provavelmente tem o dobro do andamento detectado.
RAZAO_DOBRO = 0.7
BPM_MAX_PARA_DOBRAR = 100.0


def _forca_em(envelope: np.ndarray, tempos: np.ndarray, t: float) -> float:
    sel = (tempos >= t - JANELA) & (tempos <= t + JANELA)
    return float(envelope[sel].max()) if sel.any() else 0.0


def envelope_de_ataques(sinal: np.ndarray, sr: int, fmax: float | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Força de ataque por quadro (opcionalmente só nas frequências graves) e o tempo de cada quadro."""
    if fmax is None:
        env = librosa.onset.onset_strength(y=sinal, sr=sr, hop_length=SALTO)
    else:
        # Energia (linear) só nos graves e quanto ela sobe de um quadro para o outro.
        # Em escala linear, o vazamento de notas agudas nos graves não conta.
        espectro = np.abs(librosa.stft(sinal, n_fft=2048, hop_length=SALTO))
        freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
        energia = espectro[freqs <= fmax].sum(axis=0)
        env = np.maximum(0.0, np.diff(energia, prepend=energia[:1]))
    return env, librosa.frames_to_time(np.arange(len(env)), sr=sr, hop_length=SALTO)


def corrigir_andamento(batidas: np.ndarray, envelopes: list[tuple[np.ndarray, np.ndarray]]) -> np.ndarray:
    """Dobra a grade quando o rastreador pegou só um tempo a cada dois.

    O erro típico é se prender só na caixa (tempos 2 e 4), que soa bem mais forte que
    o bumbo: aí o bumbo cai no meio de cada "tempo". `envelopes` são pares (força, tempos)
    da bateria (os graves e, se houver faixa isolada, a bateria inteira); basta num deles
    o meio de cada tempo ter ataques quase tão fortes quanto os tempos.
    """
    if len(batidas) < 4:
        return batidas
    intervalo = float(np.median(np.diff(batidas)))
    if 60.0 / intervalo > BPM_MAX_PARA_DOBRAR:
        return batidas
    meios = (batidas[:-1] + batidas[1:]) / 2
    razao = 0.0
    for envelope, tempos in envelopes:
        if envelope.max() <= 0:
            continue
        nos_tempos = np.mean([_forca_em(envelope, tempos, b) for b in batidas])
        nos_meios = np.mean([_forca_em(envelope, tempos, m) for m in meios])
        # Ataques no meio dos tempos precisam ser de verdade (bumbo), e não só ruído de fundo
        relevante = nos_meios >= 0.25 * np.percentile(envelope, 99)
        if nos_tempos > 0 and relevante:
            razao = max(razao, nos_meios / nos_tempos)
    if razao < RAZAO_DOBRO:
        return batidas
    dobrado = np.empty(len(batidas) + len(meios))
    dobrado[0::2] = batidas
    dobrado[1::2] = meios
    return dobrado


def completar_bordas(batidas: np.ndarray, sinal: np.ndarray, sr: int) -> np.ndarray:
    """Recupera os tempos do começo e do fim que o rastreador deixou de fora.

    Continua a grade para trás e para a frente, no mesmo intervalo, enquanto há som.
    """
    if len(batidas) < 2:
        return batidas
    rms = librosa.feature.rms(y=sinal, hop_length=SALTO)[0]
    t_rms = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=SALTO)
    piso = 0.1 * float(np.median(rms[rms > 0])) if (rms > 0).any() else 0.0
    duracao = len(sinal) / sr

    def tem_som(t: float, passo: float) -> bool:
        # Som logo no tempo (e não só perto dele): evita criar tempos no silêncio antes da música
        sel = (t_rms >= t - 0.03) & (t_rms < t + min(0.15, passo / 3))
        return bool(sel.any() and rms[sel].max() > piso)

    inicio = int(np.clip(4, 2, len(batidas)))
    passo_ini = float(np.median(np.diff(batidas[:inicio])))
    passo_fim = float(np.median(np.diff(batidas[-inicio:])))
    antes = []
    t = float(batidas[0]) - passo_ini
    while t >= -0.02 and tem_som(max(0.0, t), passo_ini):
        antes.append(max(0.0, t))
        t -= passo_ini
    depois = []
    t = float(batidas[-1]) + passo_fim
    while t < duracao - 0.05 and tem_som(t, passo_fim):
        depois.append(t)
        t += passo_fim
    return np.concatenate([antes[::-1], batidas, depois])


def ataques(sinal: np.ndarray, sr: int, salto: int = 128, sensibilidade: float = 0.08) -> np.ndarray:
    """Tempos (s) dos ataques de verdade: picos da força de ataque acima da média local.

    O limiar acompanha o nível do trecho, então o "chiado" constante de uma faixa
    separada (vazamento, cordas soando) não vira ataque.
    """
    if np.abs(sinal).sum() == 0:
        return np.array([])
    env = librosa.onset.onset_strength(y=sinal, sr=sr, hop_length=salto)
    if env.max() <= 0:
        return np.array([])
    env = env / env.max()
    fps = sr / salto
    media = max(1, int(0.12 * fps))
    picos = librosa.util.peak_pick(
        env, pre_max=3, post_max=3, pre_avg=media, post_avg=media,
        delta=sensibilidade, wait=max(1, int(0.06 * fps)),
    )
    # O pico da força vem depois do início do som: recua até onde a subida passa de 30%
    janela = max(2, int(0.04 * fps))
    inicios = []
    for p in picos:
        base = float(env[max(0, p - janela):p + 1].min())
        limiar = base + 0.3 * (env[p] - base)
        j = p
        while j > 0 and p - j < janela and env[j - 1] > limiar:
            j -= 1
        inicios.append(j)
    return librosa.frames_to_time(np.array(inicios, dtype=int), sr=sr, hop_length=salto)


def alinhar_aos_ataques(batidas: np.ndarray, sinal: np.ndarray, sr: int) -> np.ndarray:
    """Encosta a grade nos ataques que se ouvem.

    O rastreador marca o tempo no pico da força de ataque, que vem depois do início
    do som: ~25 ms em áudio sintético e ~58 ms nas músicas reais testadas, o bastante
    para a batida parecer "atrasada". Corrige o atraso médio e depois encaixa cada
    tempo no ataque mais próximo, se houver um bem perto.
    """
    if len(batidas) < 4:
        return batidas
    picos = ataques(sinal, sr)
    if len(picos) == 0:
        return batidas

    def mais_proximo(t: float) -> float:
        return float(picos[np.argmin(np.abs(picos - t))])

    desvios = [mais_proximo(b) - b for b in batidas]
    desvios = [d for d in desvios if abs(d) <= 0.08]
    if len(desvios) < len(batidas) // 3:
        return batidas
    ajuste = float(np.median(desvios))
    alinhadas = []
    for b in batidas + ajuste:
        p = mais_proximo(b)
        alinhadas.append(p if abs(p - b) <= 0.025 else b)
    return np.maximum.accumulate(np.maximum(np.array(alinhadas), 0.0))


def detectar_tempo_forte(
    batidas: np.ndarray,
    envelope_grave: np.ndarray,
    tempos_env: np.ndarray,
    trocas_de_acorde: list[float] | None = None,
    envelope_baixo: np.ndarray | None = None,
) -> int:
    """Índice (0 a 3), dentro de `batidas`, do primeiro tempo "1" do compasso (4/4).

    Junta o que um músico usa para achar o "1": o bumbo e o baixo atacam mais forte
    no 1, e os acordes quase sempre trocam no 1. O bumbo sozinho confunde o 1 com o 3;
    as trocas de acorde desempatam.
    """
    n = len(batidas)
    if n < 8:
        return 0

    def perfil(envelope: np.ndarray | None) -> np.ndarray:
        if envelope is None or envelope.max() <= 0:
            return np.zeros(4)
        forca = np.array([_forca_em(envelope, tempos_env, b) for b in batidas])
        media = forca.mean() or 1.0
        return np.array([forca[f::4].mean() / media for f in range(4)])

    pontos = perfil(envelope_grave) + 0.5 * perfil(envelope_baixo)
    if trocas_de_acorde:
        contagem = np.zeros(4)
        for t in trocas_de_acorde:
            i = int(np.argmin(np.abs(batidas - t)))
            if abs(batidas[i] - t) < 0.15:
                contagem[i % 4] += 1
        if contagem.sum() > 0:
            pontos += 1.5 * contagem / contagem.sum()
    return int(np.argmax(pontos))


def posicao_em_tempos(t: float | np.ndarray, batidas: list[float] | np.ndarray) -> float | np.ndarray:
    """Converte segundos em tempos da música (0 = primeira batida), seguindo as batidas reais.

    Entre duas batidas, interpola; antes da primeira e depois da última, continua no
    intervalo da borda.
    """
    b = np.asarray(batidas, dtype=float)
    if len(b) < 2:
        return np.asarray(t, dtype=float) * 0.0
    x = np.asarray(t, dtype=float)
    pos = np.interp(x, b, np.arange(len(b), dtype=float))
    pos = np.where(x < b[0], (x - b[0]) / (b[1] - b[0]), pos)
    pos = np.where(x > b[-1], len(b) - 1 + (x - b[-1]) / (b[-1] - b[-2]), pos)
    return float(pos) if np.ndim(pos) == 0 else pos


def origem_dos_compassos(tempo_forte: int) -> int:
    """Índice da batida em que começa o 1º compasso da tablatura e da partitura.

    Com tempos antes do primeiro "1" (anacruse), o 1º compasso começa 4 tempos antes,
    com pausa nos tempos que faltam. O site usa a mesma regra para o cursor.
    """
    return tempo_forte - 4 if tempo_forte > 0 else 0


def bpm_das_batidas(batidas: np.ndarray, padrao: float) -> float:
    """Andamento médio da gravação: inclinação da reta que passa pelas batidas.

    Cada batida tem um erro de até meio quadro de análise (~12 ms); a reta usa todas
    e cancela esse erro, que a mediana dos intervalos deixa passar (ex.: 99,4 em vez de 100).
    """
    b = np.asarray(batidas, dtype=float)
    if len(b) < 2:
        return padrao
    if len(b) < 4:
        return 60.0 / float(np.median(np.diff(b)))
    intervalo = float(np.polyfit(np.arange(len(b)), b, 1)[0])
    return 60.0 / intervalo if intervalo > 0 else padrao
