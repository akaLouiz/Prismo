# Decisões do Prismo

Registro das decisões de produto e de tecnologia, para lembrar o porquê de cada escolha.

## Produto

- **Nome: Prismo.** Um prisma separa a luz em cores, o Prismo separa a música em instrumentos. Há um registro "PRISMO" da Carl Zeiss na classe 9 (máquinas de medição), segmento sem relação com música; as classes 41 e 42 estavam livres na consulta ao INPI. Confirmar a viabilidade com um agente de propriedade industrial antes de depositar.
- **Foco inicial: violão e guitarra.** Stems, cifra com letra e tablatura. Outros instrumentos entram depois.
- **Diferencial frente a Moises e Klangio:** separar primeiro e transcrever a faixa limpa depois, entregando material no padrão brasileiro (cifra com letra, imprimível).
- **Nichos prioritários:** violão/guitarra, ministérios de louvor, professores, bandas.
- **Direitos autorais:** o material de músicas de terceiros é só para estudo pessoal, sem compartilhamento público. Link do YouTube fica fora (termos de uso).

## Identidade visual

- Fundo `#0A0A0F`, cartões `#12121A` e `#1C1C26`, texto `#F4F4F7`.
- Espectro: `#8B5CF6` → `#EC4899` → `#3B82F6` → `#10B981`, usado só no logo, nos botões principais e na onda sonora da mistura.
- Cor fixa por instrumento: guitarra `#A78BFA`, voz `#F472B6`, baixo `#60A5FA`, bateria `#34D399`.
- Tipografia: Space Grotesk (títulos), Inter (interface), JetBrains Mono (cifra e tablatura).

## Tecnologia

- **Motor em Python** (`engine/`), separado do site, para rodar em servidores com GPU.
- **Separação:** Demucs `htdemucs_6s` (6 faixas).
- **Transcrição:** Basic Pitch (Spotify), seguida de limpeza de harmônicos própria.
- **Acordes e tom:** linha de base clássica (cromagrama + Viterbi + perfis de Krumhansl), com desempate de tons relativos. Substituível por um modelo treinado sem mudar o resto.
- **Ritmo:** o rastreador de batidas do librosa, com três correções próprias (`ritmo.py`): dobra o andamento quando ele se prende só na caixa (com evidência do bumbo), recupera os tempos do começo e do fim, e acha o "1" do compasso pelo bumbo, pelo baixo e pelas trocas de acorde. Levada, tablatura, partitura e cifra seguem a lista real de batidas, não um BPM fixo, que se afasta da gravação com o tempo.
- **Tablatura:** programação dinâmica própria sobre (forma, posição da mão).
- **Partitura:** music21 gerando MusicXML e MIDI; o site vai renderizar com OpenSheetMusicDisplay ou Verovio.
