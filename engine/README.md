# Motor de áudio do Prismo

Recebe um áudio ou vídeo e entrega:

| Saída | Arquivo |
|---|---|
| Faixas separadas (voz, guitarra, baixo, bateria, piano, outros) | `faixas/*.wav` |
| Cifra no padrão brasileiro, com tom e sugestão de capotraste | `cifra.txt` |
| Tablatura (guitarra, violão e baixo) | `tablatura.txt` |
| Partitura | `partitura.musicxml` (abre no MuseScore) e `partitura.mid` |
| Tudo em dados, para o site | `resultado.json` |

## Como funciona

```
áudio/vídeo
   │  ffmpeg (só para vídeo)
   ▼
separação ─────────── Demucs (htdemucs_6s)
   │
   ├─ faixas harmônicas ──► análise: BPM, tom, acordes (librosa + Viterbi)
   ├─ voz ────────────────► letra com tempo (Whisper)
   └─ instrumento ────────► notas (Basic Pitch) ─► limpeza de harmônicos
                                                    │
                          ┌─────────────────────────┼──────────────────────┐
                          ▼                         ▼                      ▼
                    cifra com letra       tablatura (posição da mão)   partitura
```

O que é nosso e é o diferencial técnico:

- **Tablatura com "mão virtual"**: o algoritmo testa todas as cordas e casas possíveis para cada nota e escolhe a sequência que um guitarrista tocaria, modelando a mão como uma janela de 4 casas. Uma escala sai na "caixa" certa, e acordes saem em formas abertas quando possível.
- **Limpeza de notas fantasmas**: remove harmônicos que o modelo confunde com notas tocadas.
- **Cifra brasileira**: notação `7M`, `°`, sustenido ou bemol conforme o tom, desempate entre tons relativos (Sol maior x Mi menor) e capotraste sugerido.

## Instalação no seu computador

### 1. Pré-requisitos

- **Python 3.11** (importante: o Basic Pitch ainda não funciona no 3.13). No Windows, baixe em https://www.python.org/downloads/release/python-3119/ e marque **"Add python.exe to PATH"** na instalação.
- **ffmpeg**, só se for enviar vídeo. No Windows: `winget install ffmpeg`.
- **Git**: https://git-scm.com/downloads

### 2. Baixar o projeto e instalar

No terminal (no Windows, o **PowerShell**):

```bash
git clone https://github.com/akaLouiz/prismo.git
cd prismo/engine
py -3.11 -m venv .venv            # no Mac/Linux: python3.11 -m venv .venv
.venv\Scripts\activate            # no Mac/Linux: source .venv/bin/activate
pip install -e ".[completo,dev]"
```

A primeira instalação baixa o PyTorch e leva alguns minutos. Na primeira música processada, o Demucs e o Whisper também baixam os modelos (algumas centenas de MB, só uma vez).

Tem placa de vídeo NVIDIA? Instale o PyTorch com suporte a GPU antes do passo acima, seguindo https://pytorch.org/get-started/locally/. A separação fica de 10 a 20 vezes mais rápida.

### 3. Processar uma música

```bash
prismo minha-musica.mp3 --instrumento guitarra
prismo ensaio.mp4 --instrumento violao
prismo musica.wav --instrumento baixo --sem-letra
```

Os resultados vão para `saida/<nome-da-musica>/`. Instrumentos: `guitarra`, `violao`, `baixo`, `voz`, `piano`.

Opções úteis:

- `--sem-separacao`: pula a separação (bem mais rápido, menos preciso)
- `--sem-letra`: não reconhece a letra
- `--dispositivo cuda`: força o uso da GPU

## API (o que o site chama)

O motor também roda como servidor HTTP, que é como o site no Lovable vai usá-lo. O contrato completo está em [`docs/contrato-api.md`](../docs/contrato-api.md).

Para rodar localmente:

```bash
pip install -e ".[completo]"
cp .env.exemplo .env          # preencha PRISMO_TOKEN e os dados do Supabase
prismo-api                    # sobe em http://localhost:8000
```

Teste com `http://localhost:8000/saude`. Em produção, use o `Dockerfile` num servidor com GPU NVIDIA: ele já instala tudo e baixa os modelos durante a construção.

## Testes

```bash
pytest
```

Os testes geram áudio sintético com acordes conhecidos e verificam andamento, tom, acordes, tablatura, cifra e partitura.

## Limitações conhecidas (próximos passos)

- Acordes: o reconhecimento atual é por modelos de acordes (maior, menor, 7, 7M, m7). Um modelo treinado vai trazer inversões (D/F#), sus e dim.
- Compasso: assume 4/4, e o primeiro tempo é a primeira batida detectada.
- Estrutura (intro, verso, refrão) ainda não é detectada.
- Separar violão de guitarra na mesma gravação é difícil para o Demucs: os dois tendem a sair juntos na faixa `guitarra`.
