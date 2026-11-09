# Contrato entre o site e o motor de áudio

Este é o "combinado" entre o site (Lovable + Supabase) e o motor (`engine/`). Enquanto ele não mudar, os dois lados podem evoluir separados.

## Visão geral

```
Site (Supabase)                                   Motor (servidor com GPU)
───────────────                                   ────────────────────────
1. usuário envia o arquivo → bucket "uploads"
2. edge function process-song ── POST /processar ──►  responde 202 na hora
                                                      coloca na fila
3. edge function engine-callback ◄── progresso ─────  a cada etapa
                                 ◄── progresso ─────
                                                      envia faixas → bucket "stems"
                                                      envia arquivos → bucket "results"
4. salva resultado, status "pronto" ◄── concluido ──  (ou "erro")
```

## Autenticação

- O site chama o motor com `Authorization: Bearer <PRISMO_TOKEN>`.
- O motor chama o callback com `Authorization: Bearer <PRISMO_CALLBACK_TOKEN>` (se não for definido, é o mesmo `PRISMO_TOKEN`). A edge function `engine-callback` deve recusar com 401 qualquer chamada sem esse token.
- Por segurança, `audio_url` precisa ser `https` e do host do Supabase do projeto (`PRISMO_HOSTS_PERMITIDOS`), e `callback_url` precisa ser `https` e de um host da lista `PRISMO_HOSTS_CALLBACK` (coloque ali o domínio do site).

## `POST /processar`

Corpo:

```json
{
  "song_id": "uuid-da-musica",
  "audio_url": "https://SEU-PROJETO.supabase.co/storage/v1/object/sign/uploads/...?token=...",
  "instrumento": "violao",
  "letra": true,
  "separar": true,
  "callback_url": "https://SEU-PROJETO.supabase.co/functions/v1/engine-callback",
  "nome_arquivo": "ensaio-domingo.mp3",
  "pasta_destino": "uuid-do-usuario/uuid-da-musica",
  "uploads": {
    "faixas/voz": "https://SEU-PROJETO.supabase.co/storage/v1/object/upload/sign/stems/<pasta>/voz.mp3?token=...",
    "arquivos/cifra": "https://SEU-PROJETO.supabase.co/storage/v1/object/upload/sign/results/<pasta>/cifra.txt?token=..."
  }
}
```

- `song_id`: letras, números, `-` e `_`, até 64 caracteres (o UUID do Supabase serve).
- `audio_url`: URL assinada do bucket `uploads`, válida por pelo menos 1 hora.
- `instrumento`: `guitarra`, `violao`, `baixo`, `voz` ou `piano`.
- `nome_arquivo`: nome original, usado no resultado e para descobrir o formato.
- `uploads`: um link de envio assinado por arquivo, gerado pelo site com `createSignedUploadUrl` (vale 2 horas e só para aquele arquivo). Chaves: `faixas/<voz|guitarra|baixo|bateria|piano|outros>` e `arquivos/<cifra|tablatura|musicxml|midi>`. Com eles, o motor não precisa de nenhuma chave do Supabase. Sem eles, o motor usa `SUPABASE_SERVICE_ROLE_KEY`, se estiver configurada.
- `pasta_destino`: pasta, dentro dos buckets, onde faixas e arquivos são salvos. O Storage do site só deixa cada usuário abrir a pasta que começa com o próprio id, então use `<id do usuário>/<id da música>`. Padrão: o `song_id`.

Resposta `202`:

```json
{ "song_id": "uuid-da-musica", "status": "na_fila", "posicao_na_fila": 1, "novo": true, "etapa": null, "mensagem": null, "erro": null }
```

Se a mesma música já estiver na fila ou processando, a resposta é a mesma com `"novo": false`, e ela não é processada duas vezes.

Erros: `401` (token inválido), `400` (endereço não permitido), `422` (campos inválidos).

## Callbacks (o motor chama o site)

Sempre `POST` em `callback_url`, JSON, com o token no cabeçalho. Responda `200` rápido. O resultado final e os erros são reenviados até 5 vezes se o site não responder `2xx`.

### Progresso

```json
{ "tipo": "progresso", "song_id": "uuid", "etapa": "separacao", "mensagem": "Separando as faixas" }
```

Etapas, nesta ordem (algumas podem não acontecer, conforme as opções):

| etapa | mensagem |
|---|---|
| `preparo` | Preparando o áudio |
| `separacao` | Separando as faixas |
| `analise` | Analisando tom e acordes |
| `letra` | Reconhecendo a letra |
| `transcricao` | Transcrevendo as notas |
| `materiais` | Montando cifra, tablatura e partitura |

O site deve gravar `etapa` em `songs.etapa_atual`.

### Concluído

```json
{ "tipo": "concluido", "song_id": "uuid", "resultado": { ... } }
```

O `resultado` segue o formato descrito no prompt do Lovable, com estes detalhes:

- `faixas`: caminho de cada faixa **dentro do bucket `stems`**, ex.: `{ "voz": "<pasta_destino>/voz.mp3", "guitarra": "<pasta_destino>/guitarra.mp3", ... }`. Vazio se a separação foi desligada.
- `arquivos`: caminho de cada material **dentro do bucket `results`**, ex.: `{ "cifra": "<pasta_destino>/cifra.txt", "tablatura": "<pasta_destino>/tablatura.txt", "musicxml": "<pasta_destino>/partitura.musicxml", "midi": "<pasta_destino>/partitura.mid" }`.
- `buckets`: `{ "faixas": "stems", "arquivos": "results" }`.
- `tempo_total`: segundos de processamento.
- `batidas`: o tempo (em segundos) de cada batida da música, na ordem. É a grade real da gravação: o andamento de quem toca varia um pouco, então o site deve seguir esta lista (interpolando entre duas batidas) para o metrônomo, o destaque da batida e o cursor da partitura, e não uma conta fixa com o `bpm`.
- `tempo_forte`: índice, em `batidas`, do primeiro "1" do compasso (0 a 3). As batidas antes dele são uma anacruse (a música entrou no fim de um compasso). Os compassos contam de 4 em 4 a partir daqui. O 1º compasso da tablatura e da partitura começa na batida `tempo_forte - 4` quando `tempo_forte > 0` (com pausa nos tempos que faltam), ou na batida 0. Ausente em resultados antigos: trate como 0.
- `golpes`: cada ataque do violão/guitarra na faixa isolada, em ordem: `[{ "t": segundos, "dir": "baixo" | "cima" }]`. É o que o violão toca de fato, compasso a compasso; o site acende a seta no instante de cada golpe. A direção segue a convenção do violão popular (desce no tempo, sobe no contratempo da menor subdivisão usada). Lista vazia quando o instrumento não é violão/guitarra ou não há faixa isolada; ausente em resultados antigos.
- `levada`: a batida que o violão/guitarra toca, detectada na faixa isolada: `{ "padrao": [8 x "baixo" | "cima" | "pausa"], "confianca": 0..1, "compassos": n }` (a 1ª colcheia é o "1" do compasso, ver `tempo_forte`), ou `null` quando não dá para dizer (sem separação, instrumento que não é violão/guitarra, trecho sem levada regular).
- `idioma_letra`: idioma em que a letra foi cantada (código ISO, ex.: `"en"`), detectado pelo motor; a letra vem nesse idioma, sem tradução.
- `avisos`: lista de avisos para mostrar ao usuário (ex.: letra não reconhecida).

O site deve: salvar `resultado` em `songs.resultado`, preencher `bpm`, `tom` (= `resultado.tom.cifra`) e `duracao`, inserir uma linha em `stems` para cada item de `faixas` e mudar o status para `pronto`.

### Erro

```json
{ "tipo": "erro", "song_id": "uuid", "mensagem": "Formato de arquivo não suportado. Envie MP3, WAV, M4A, OGG, FLAC, MP4, MOV ou WEBM." }
```

A `mensagem` já é amigável e pode ser mostrada ao usuário. O site muda o status para `erro` e grava a mensagem em `songs.erro_mensagem`.

## Outras rotas

- `GET /saude` (sem token): `{ "ok": true, "versao": "0.1.0", "fila": 0, "recursos": { "separacao": true, "transcricao": true, "letra": true, "ffmpeg": true, "gpu": true } }`
- `GET /status/{song_id}` (com token): o estado atual da música no motor. Útil se um callback se perder.
