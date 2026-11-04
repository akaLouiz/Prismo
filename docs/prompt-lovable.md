# Prompt para o Lovable: plataforma Prismo

Copie tudo abaixo da linha e cole no Lovable como primeira mensagem.

---

Crie a plataforma web completa **Prismo**, em português do Brasil, seguindo exatamente esta especificação. Construa tudo: identidade visual, todas as páginas, autenticação, banco de dados, armazenamento de arquivos, integração com o motor de processamento e um modo demonstração funcional. Não simplifique telas nem pule seções. Use React + TypeScript + Tailwind + shadcn/ui, com Supabase (Lovable Cloud) para autenticação, banco e storage.

## 1. O produto

O Prismo é uma plataforma para músicos. O usuário envia um áudio ou vídeo de uma música, escolhe o seu instrumento, e a plataforma:

1. separa as faixas (voz, guitarra, baixo, bateria, piano, outros);
2. detecta tom, andamento (BPM), compasso e acordes;
3. entrega material pronto para tocar: **cifra com letra no padrão brasileiro**, **tablatura** (guitarra, violão, baixo) e **partitura** (MusicXML), com exportação em PDF, MIDI e MusicXML.

Conceito da marca: "Um prisma separa a luz em cores. O Prismo separa a música em instrumentos." Cada instrumento tem uma cor fixa do espectro, e essa cor aparece em todo o produto: mixer, ondas sonoras, cifra, tablatura e partitura.

Público: violonistas e guitarristas, ministérios de louvor, professores de música, bandas e compositores.

## 2. Identidade visual (obrigatório seguir à risca)

### Cores (defina como tokens CSS e no tailwind.config)

O site é **sempre escuro**, preto neutro levemente azulado. Não crie tema claro.

| Token | Hex | Uso |
|---|---|---|
| `bg` | `#0A0A0F` | fundo da página |
| `surface` | `#12121A` | cartões, painéis |
| `surface-2` | `#1C1C26` | elementos elevados, itens selecionados, inputs |
| `border` | `#23232F` | bordas de cartões |
| `border-strong` | `#2A2A36` | bordas de botões e inputs |
| `text` | `#F4F4F7` | texto principal |
| `text-2` | `#B4B4C2` | texto secundário |
| `text-3` | `#9A9AAB` | legendas, rótulos |
| `muted` | `#8A8A9A` | texto de rodapé |

**Espectro (degradê da marca):** `linear-gradient(90deg, #8B5CF6 0%, #EC4899 35%, #3B82F6 68%, #10B981 100%)`. Use o degradê completo **com moderação**: no logo, no botão principal de cada tela, no destaque do título da landing, na onda sonora da música original e na borda do bloco de chamada final. Nunca como fundo de seção inteira.

Botão primário: `linear-gradient(90deg, #8B5CF6, #EC4899)`, texto branco, totalmente arredondado (pill), altura 52px na landing e 46px no app.

**Cores dos instrumentos (fixas em todo o produto):**

| Faixa | Cor | Fundo de chip | Texto de chip |
|---|---|---|---|
| Guitarra / violão | `#A78BFA` | `#1E1830` | `#C4B5FD` |
| Voz | `#F472B6` | `#2A1624` | `#F9A8D4` |
| Baixo | `#60A5FA` | `#14203A` | `#93C5FD` |
| Bateria | `#34D399` | `#10271F` | `#6EE7B7` |
| Piano | `#FBBF24` | `#2A2110` | `#FCD34D` |
| Outros | `#94A3B8` | `#1A1F28` | `#CBD5E1` |

### Tipografia (Google Fonts)

- **Space Grotesk** (400, 500, 700): títulos e logotipo. Títulos com peso 500 e letter-spacing negativo (-1px a -2.5px).
- **Inter** (400, 500, 600): interface e textos.
- **JetBrains Mono** (400, 600): cifra, tablatura, tempos, BPM, códigos de tom. Obrigatório na cifra, para os acordes alinharem exatamente sobre a sílaba.

Rótulos de seção: Inter 13px, peso 600, letter-spacing 2px, caixa alta, cor `text-3` (ex.: "COMO FUNCIONA").

### Logo

O logotipo é a palavra **prismo** em minúsculas (Space Grotesk 500), precedida do símbolo: uma linha branca horizontal entrando num triângulo de contorno branco e saindo como quatro linhas coloridas em leque. Use exatamente este SVG como componente `<Logo />`:

```svg
<svg viewBox="0 0 260 140" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
  <line x1="0" y1="78" x2="102" y2="78" stroke="#F4F4F7" stroke-width="10" stroke-linecap="round"/>
  <path d="M130 14 L184 118 L76 118 Z" fill="none" stroke="#F4F4F7" stroke-width="10" stroke-linejoin="round"/>
  <line x1="150" y1="78" x2="256" y2="34" stroke="#A78BFA" stroke-width="10" stroke-linecap="round"/>
  <line x1="152" y1="84" x2="256" y2="72" stroke="#F472B6" stroke-width="10" stroke-linecap="round"/>
  <line x1="152" y1="88" x2="256" y2="100" stroke="#60A5FA" stroke-width="10" stroke-linecap="round"/>
  <line x1="150" y1="92" x2="256" y2="128" stroke="#34D399" stroke-width="10" stroke-linecap="round"/>
</svg>
```

Favicon e ícone: quadrado arredondado com o degradê do espectro (135°) e o triângulo em contorno branco no centro.

### Estilo geral

- Cartões: fundo `surface`, borda 1px `border`, raio 20px (16px em itens menores, 12px em controles).
- Sem sombras pesadas, sem glassmorphism, sem emojis. Ícones: lucide-react, traço fino.
- Muito espaço em branco. Conteúdo centralizado com `max-width: 1200px` e margens laterais de 24px.
- Animações sutis (150–250 ms): hover em botões, troca de abas, entrada das faixas no mixer.
- Totalmente responsivo: no celular, menus empilham, tabelas e tablaturas rolam horizontalmente dentro de uma caixa, o mixer vira lista vertical.
- Acessível: contraste mínimo 4.5:1, botões reais com `aria-label` nos que têm só ícone, foco visível (anel `#8B5CF6`), navegação por teclado.

## 3. Páginas e rotas

### 3.1 Landing page (`/`)

Em ordem:

1. **Cabeçalho**: logo à esquerda; links "Como funciona", "Recursos", "Para quem", "Planos" (rolam até as seções); à direita "Entrar" (texto) e "Começar grátis" (botão com borda pill). Fica fixo no topo com fundo `bg` semitransparente e blur leve ao rolar.
2. **Hero** centralizado: selo "EM BREVE · ACESSO ANTECIPADO" (pill com borda `#2E2A44`, texto `#C4B5FD`); título em Space Grotesk, até 88px: "Envie a música." e, na linha de baixo, **"Receba cada instrumento."** com o degradê do espectro aplicado ao texto; subtítulo "O Prismo separa voz, guitarra, baixo e bateria de qualquer gravação sua e entrega cifra, tablatura e partitura prontas para tocar."; formulário de e-mail + botão primário "Quero testar primeiro" (salva na tabela `waitlist`, mostra toast de sucesso, valida e-mail); legenda "Grátis para os primeiros testadores. Sem cartão."
3. **Demonstração animada** (o momento-assinatura do produto): cartão grande com o arquivo "ensaio-domingo.mp3 · Mi menor · 92 BPM · 4/4". Mostra uma onda sonora em barras com o degradê do espectro (cada barra com a cor interpolada pela posição). Ao entrar na tela (IntersectionObserver), a onda "se abre": uma seta aparece e surgem quatro faixas empilhadas (Guitarra, Voz, Baixo, Bateria), cada uma com bolinha e barras na sua cor, entrando uma após a outra.
4. **Como funciona** (`#como`): rótulo, título "Da gravação no celular ao material na estante." e três cartões numerados em JetBrains Mono (01 roxo, 02 rosa, 03 verde): "Envie o áudio ou vídeo", "O Prismo separa as faixas", "Toque, ajuste e imprima".
5. **Recursos** (`#recursos`): duas colunas. À esquerda, rótulo "CIFRA DO JEITO BRASILEIRO", título "Acorde em cima da sílaba certa. Tom do cantor em um clique.", texto e chips (Cifra com letra, Tablatura, Partitura, Mudança de tom) nas cores dos instrumentos. À direita, cartão com cifra de exemplo (acordes em roxo, letra em branco, mono) e tablatura em rosa, com botões "Tom: Em" e "Capo 2". Use **letra original inventada**, nunca letra de música real.
6. **Para quem** (`#para-quem`): quatro cartões com uma barrinha colorida no topo: Violão e guitarra, Ministérios de louvor, Professores, Bandas e compositores.
7. **Planos** (`#planos`): três cartões (Grátis R$ 0; Músico R$ 19,90/mês com selo "Mais escolhido" e borda 2px `#8B5CF6`; Professor e banda R$ 49,90/mês), cada um com lista de recursos e botão. Deixe os valores em uma constante fácil de editar.
8. **Chamada final**: bloco com borda de 2px em degradê do espectro, título "Seja um dos primeiros a testar.", formulário de e-mail com botão branco.
9. **Rodapé**: "Prismo · feito no Brasil para quem toca", links para Termos, Privacidade e Contato, e o aviso "Transcrição automática: revise antes de apresentar."

### 3.2 Autenticação (`/entrar`, `/cadastro`, `/recuperar-senha`)

Tela dividida: à esquerda o formulário (e-mail e senha, "Continuar com Google"), à direita um painel `surface` com o logo grande e a frase do conceito. Após o cadastro, criar o `profile` com o nome, o instrumento principal (select) e o plano `gratis`.

### 3.3 App: layout com barra lateral (rotas `/app/*`, protegidas)

Barra lateral (260px no desktop; vira menu inferior no celular):

- logo;
- botão primário "+ Nova música";
- navegação: Biblioteca, Repertórios, Configurações;
- lista "SUA BIBLIOTECA" com as últimas músicas (nome, tom e BPM em `text-3`);
- no rodapé, cartão de uso do plano: "Plano grátis", barra de progresso com o degradê e "3 de 5 músicas usadas este mês", com link "Fazer upgrade".

### 3.4 Biblioteca (`/app`)

Grade de cartões das músicas do usuário: nome, data, duração, tom, BPM, instrumento escolhido, status (chip "Processando", "Pronto" ou "Erro") e uma mini onda colorida. Busca por nome, filtro por instrumento e por status, ordenação. Estado vazio convidativo: "Envie sua primeira música" com botão. Menu de cada cartão: abrir, renomear, mover para repertório, excluir (com confirmação).

### 3.5 Nova música (`/app/nova`)

Fluxo em 3 passos com indicador de progresso:

1. **Arquivo**: área grande de arrastar e soltar (borda tracejada, ícone de música) que aceita MP3, WAV, M4A, OGG, FLAC, MP4, MOV e WEBM, até 50 MB e 10 minutos. Mostra nome, tamanho, duração e um player de pré-visualização.
2. **Instrumento**: cartões selecionáveis grandes, cada um com ícone e cor: Guitarra, Violão, Baixo, Voz, Piano. Opções extras: "Reconhecer a letra" (switch, ligado), "Separar faixas" (switch, ligado).
3. **Confirmação**: checkbox obrigatório "Este material é para meu estudo pessoal e não será redistribuído", resumo e botão primário "Processar música".

Ao enviar: upload para o bucket `uploads` com barra de progresso, criação do registro em `songs` com status `processando`, chamada da edge function `process-song` e redirecionamento para a tela de processamento.

### 3.6 Processando (`/app/musica/:id`, enquanto status = processando)

Tela centralizada com o símbolo do prisma animado (a linha branca entra e as quatro cores pulsam em sequência) e as etapas com check em tempo real (Realtime do Supabase na tabela `songs`): "Preparando o áudio", "Separando as faixas", "Analisando tom e acordes", "Reconhecendo a letra", "Transcrevendo as notas", "Montando cifra, tablatura e partitura". Texto: "Isso leva de 1 a 3 minutos. Você pode sair desta tela; avisamos quando ficar pronto."

### 3.7 Estúdio (`/app/musica/:id`, quando status = pronto): a tela principal do produto

**Topo**: nome da música (editável inline, Space Grotesk 30px), linha "Tom original Em · 92 BPM · 4/4 · 3:48" e botões "Exportar PDF", "MIDI", "MusicXML" e "Compartilhar com a turma" (planos pagos).

**Mixer** (cartão `surface`):

- botão redondo branco de tocar/pausar (52px), tempo atual / total em mono, barra de progresso clicável;
- velocidade: botões 0.5x, 0.75x, 1x, 1.25x (o selecionado com fundo `#2E2A44` e borda `#8B5CF6`), alterando a velocidade **sem mudar o tom** (`preservesPitch`);
- botão de loop: o usuário arrasta na onda para marcar um trecho A–B e ele repete;
- metrônomo (liga/desliga, clique sincronizado com o BPM);
- **uma linha por faixa**: bolinha e nome na cor do instrumento, botões **M** (mudo: fundo branco quando ativo) e **S** (solo: fundo na cor da faixa quando ativo), controle de volume, onda sonora da faixa (wavesurfer.js) na cor do instrumento (parte já tocada na cor cheia, o resto em `#3A3A48`) e botão de baixar a faixa. Faixas mudas ficam com 22% de opacidade. Todas as faixas tocam sincronizadas (Web Audio API: um `AudioContext`, um `GainNode` por faixa).

**Seletor de material**: controle segmentado "Cifra | Tablatura | Partitura" (o selecionado com fundo branco e texto preto) e, à direita, o controle de **Tom**: botões − e + (meio tom por clique, de -6 a +6), mostrando o tom atual em mono (ex.: "F#m (+2)") e a sugestão de capotraste ("Shapes de Em · capo 2").

**Aba Cifra**:

- cabeçalho com tom, BPM, capotraste sugerido e diagramas dos acordes usados (desenhe diagramas de violão em SVG: 6 cordas, 5 casas, bolinhas nas casas, X e O em cima, para os acordes comuns; para os demais, mostre o nome num chip);
- corpo em JetBrains Mono 17px: blocos por seção (VERSO, REFRÃO), linha de acordes em roxo `#A78BFA` peso 600 e, embaixo, a letra em `#E4E4EA`, com cada acorde alinhado exatamente sobre a palavra em que entra;
- **transposição real**: ao mudar o tom, todos os acordes mudam (incluindo baixos invertidos como D/F#), usando bemóis em tons de bemol (F, Bb, Eb, Ab, Db, Gb e menores Dm, Gm, Cm, Fm, Bbm, Ebm) e sustenidos nos outros;
- notação brasileira: maior sem sufixo, menor "m", sétima "7", sétima maior "7M", menor com sétima "m7", diminuto "°";
- **rolagem automática** sincronizada com a música, destacando o acorde atual (fundo `surface-2`), com velocidade ajustável;
- modo palco: botão de tela cheia com fonte grande, e as setas do teclado ou um pedal Bluetooth (teclas PageUp/PageDown e setas) rolam a cifra;
- edição: clicar num acorde abre um popover para trocá-lo; as correções são salvas em `song_edits`.

**Aba Tablatura**: tablatura em mono com rótulos das cordas (e B G D A E para guitarra e violão, G D A E para baixo), barras de compasso, notas na cor do instrumento, rolagem horizontal no celular e cursor vertical que acompanha a reprodução. Clicar numa nota permite editar a casa.

**Aba Partitura**: renderize o MusicXML do resultado com **OpenSheetMusicDisplay** (fundo branco dentro de um cartão com raio 16px, para leitura e impressão), com cursor seguindo a reprodução e zoom. Mostre a clave, a armadura e o compasso corretos.

**Exportação**: PDF da cifra e da tablatura gerado no navegador (layout de impressão em fundo branco, com logo pequeno e "Gerado pelo Prismo" no rodapé; no plano grátis, marca d'água discreta), download do MIDI e do MusicXML.

### 3.8 Repertórios (`/app/repertorios`)

Listas de músicas (ex.: "Culto de domingo", "Show do bar"), com nome, data e ordem arrastável (drag and drop). Cada música no repertório guarda o **tom escolhido para o cantor**. Mostra o tempo total do repertório. Modo apresentação: abre a cifra da primeira música em modo palco e avança para a próxima.

### 3.9 Configurações (`/app/configuracoes`)

Perfil (nome, foto, instrumento principal), preferências (notação com sustenido ou bemol por padrão, tamanho da fonte da cifra, mostrar diagramas), plano e uso, e "Excluir minha conta e meus arquivos" (LGPD), com confirmação.

### 3.10 Páginas legais

`/termos` e `/privacidade` com textos-modelo em português, destacando: uso do material de terceiros apenas para estudo pessoal, proibição de redistribuir conteúdo protegido, armazenamento e exclusão dos arquivos conforme a LGPD, e que a transcrição é automática e pode conter erros.

## 4. Banco de dados (Supabase) com RLS em todas as tabelas

- `profiles` (id = auth.users.id, nome, instrumento_principal, plano: 'gratis' | 'musico' | 'professor', notacao_padrao, criado_em)
- `songs` (id, user_id, titulo, arquivo_path, instrumento, opcoes jsonb, status: 'processando' | 'pronto' | 'erro', etapa_atual, erro_mensagem, duracao, bpm, tom, resultado jsonb, criado_em, atualizado_em)
- `stems` (id, song_id, faixa: 'voz' | 'guitarra' | 'baixo' | 'bateria' | 'piano' | 'outros', arquivo_path)
- `song_edits` (id, song_id, user_id, tipo: 'acorde' | 'nota' | 'letra', alvo jsonb, valor jsonb, criado_em)
- `setlists` (id, user_id, nome, criado_em) e `setlist_items` (setlist_id, song_id, ordem, tom_semitons)
- `waitlist` (email único, criado_em; insert público permitido, leitura só para admin)
- `usage` (user_id, mes, musicas_processadas), com limite por plano: grátis 5/mês, músico ilimitado, professor ilimitado

Buckets do storage: `uploads` (privado), `stems` (privado) e `results` (privado), sempre acessados por URL assinada e com políticas por `user_id`. Arquivos enviados são excluídos quando a música é excluída.

## 5. Processamento: integração com o motor de áudio

O processamento pesado (separação com Demucs, transcrição com Basic Pitch, letra com Whisper) roda num **serviço Python externo que já existe** (repositório github.com/akaLouiz/prismo, pasta `engine`). **Não tente rodar IA de áudio no Lovable.** Crie a edge function `process-song` que:

1. verifica o limite do plano em `usage`;
2. gera uma URL assinada do arquivo enviado;
3. se o secret `ENGINE_URL` existir: faz `POST {ENGINE_URL}/processar` com `{ song_id, audio_url, instrumento, letra, separar, callback_url }` e o header `Authorization: Bearer {ENGINE_TOKEN}`;
4. expõe uma segunda edge function `engine-callback`, que recebe o progresso (`{ song_id, etapa }`) e o resultado final, salva `resultado`, `bpm`, `tom` e `duracao` em `songs`, registra as faixas em `stems` e muda o status para `pronto` (ou `erro` com mensagem);
5. **se `ENGINE_URL` não existir (modo demonstração)**: simula as etapas com intervalos de ~2 segundos, atualizando `etapa_atual`, e salva como resultado o JSON de demonstração abaixo, usando o próprio arquivo enviado como faixa de todas as stems. Assim a plataforma funciona do início ao fim desde já.

### Formato do resultado (exatamente o que o motor devolve; o front deve ler este formato)

```json
{
  "arquivo": "ensaio-domingo.mp3",
  "instrumento": "violao",
  "duracao": 228.4,
  "bpm": 92.0,
  "compasso": "4/4",
  "tom": { "cifra": "Em", "nome": "Mi menor", "confianca": 0.71 },
  "capotraste": { "casa": 0, "aproveitamento": 1.0 },
  "acordes": [
    { "inicio": 0.52, "fim": 3.13, "nome": "Em", "confianca": 0.93 },
    { "inicio": 3.13, "fim": 5.74, "nome": "C", "confianca": 0.9 },
    { "inicio": 5.74, "fim": 8.35, "nome": "G", "confianca": 0.88 },
    { "inicio": 8.35, "fim": 10.96, "nome": "D", "confianca": 0.91 }
  ],
  "batidas": [0.52, 1.17, 1.82, 2.48],
  "faixas": { "voz": "voz.wav", "guitarra": "guitarra.wav", "baixo": "baixo.wav", "bateria": "bateria.wav", "piano": "piano.wav", "outros": "outros.wav" },
  "letra": [
    { "inicio": 0.6, "fim": 0.95, "texto": "Toca" },
    { "inicio": 1.0, "fim": 1.2, "texto": "de" },
    { "inicio": 1.25, "fim": 1.7, "texto": "novo," },
    { "inicio": 3.2, "fim": 3.6, "texto": "deixa" },
    { "inicio": 3.65, "fim": 3.8, "texto": "o" },
    { "inicio": 3.85, "fim": 4.3, "texto": "som" },
    { "inicio": 4.35, "fim": 4.9, "texto": "falar" }
  ],
  "notas": [ { "inicio": 0.52, "fim": 1.1, "midi": 52, "intensidade": 0.6 } ],
  "tablatura": [
    { "inicio": 0.52, "fim": 1.16, "posicoes": [ { "corda": 0, "casa": 0 }, { "corda": 2, "casa": 2 }, { "corda": 3, "casa": 0 }, { "corda": 5, "casa": 3 } ] }
  ],
  "arquivos": { "cifra": "cifra.txt", "tablatura": "tablatura.txt", "musicxml": "partitura.musicxml", "midi": "partitura.mid" },
  "avisos": []
}
```

Observações sobre o formato: `corda` 0 é a mais grave; a tablatura é desenhada com a corda mais aguda em cima; a letra vem palavra por palavra com tempo, e o front monta as linhas (nova linha quando a pausa entre palavras passa de 0.9 s ou a linha chega a 9 palavras) e alinha cada acorde sobre a palavra em que ele começa. Para o modo demonstração, monte um resultado completo com cerca de 30 segundos: verso e refrão com letra **original inventada** em português, progressão Em, C, G e D, tablatura coerente e um MusicXML simples da melodia, embutido como arquivo estático em `public/demo/`.

Crie também uma **música de demonstração** já pronta na biblioteca de todo usuário novo ("Exemplo: Toca de novo"), para que ele veja o estúdio funcionando antes de enviar a primeira música.

## 6. Qualidade

- Todo texto em português do Brasil, tom direto e amigável, sem "por favor" nem exclamações em mensagens do sistema. Botões com verbo no início ("Processar música", "Exportar PDF").
- Estados de carregamento (skeletons em `surface-2`), de vazio e de erro em todas as telas, com mensagem do que aconteceu e do que fazer.
- Toasts para confirmações ("Música enviada", "Correção salva").
- Código organizado: `src/components/brand` (Logo, Spectrum), `src/components/studio` (Mixer, StemRow, ChordSheet, TabView, ScoreView, KeyControl), `src/lib/music` (transposição, notação brasileira, montagem das linhas da cifra, capotraste) com funções puras e testáveis, `src/lib/audio` (engine de reprodução multifaixa).
- Lógica musical do front, em TypeScript: transpor acordes (inclusive com baixo, "D/F#"), escolher sustenido ou bemol pelo tom, sugerir o capotraste (a casa de 0 a 7 que deixa mais acordes em formas abertas: C, A, G, E, D, Am, Em, Dm e as sétimas abertas).
- SEO da landing: título "Prismo · cifra, tablatura e partitura a partir da sua gravação", descrição, Open Graph com imagem no estilo da marca.

Ao terminar, revise cada tela com este documento e corrija o que estiver diferente do especificado.
