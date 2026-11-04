# Prompt para o Lovable: ligação com o motor de áudio

Use este prompt quando o motor estiver no ar (servidor com GPU). Antes, adicione nos segredos do projeto no Lovable:

- `ENGINE_URL`: endereço do motor, sem barra no final (ex.: `https://prismo-engine.exemplo.com`)
- `ENGINE_TOKEN`: a mesma senha do `PRISMO_TOKEN` do motor
- `ENGINE_CALLBACK_TOKEN`: a mesma do `PRISMO_CALLBACK_TOKEN` do motor (se não usar uma separada, repita o `ENGINE_TOKEN`)

Copie tudo abaixo da linha e cole no Lovable.

---

Ajuste a integração do Prismo com o motor de áudio para seguir exatamente este contrato. Não altere o layout nem o design. Mantenha o modo demonstração funcionando quando `ENGINE_URL` não estiver definido.

## 1. Edge function `process-song`

Chamada pelo front depois do upload. Ela deve:

1. Verificar o usuário autenticado, que a música pertence a ele e o limite do plano em `usage`.
2. Gerar uma URL assinada do arquivo no bucket `uploads`, válida por 2 horas.
3. Se `ENGINE_URL` existir, chamar:

```
POST {ENGINE_URL}/processar
Authorization: Bearer {ENGINE_TOKEN}
Content-Type: application/json

{
  "song_id": "<id da música>",
  "audio_url": "<URL assinada>",
  "instrumento": "guitarra | violao | baixo | voz | piano",
  "letra": true,
  "separar": true,
  "callback_url": "<SUPABASE_URL>/functions/v1/engine-callback",
  "nome_arquivo": "<nome original do arquivo>"
}
```

4. Resposta 202: gravar em `songs` o `etapa_atual = 'na_fila'` e a posição (`posicao_na_fila`) numa nova coluna `posicao_fila` (integer). Resposta 401, 400, 422 ou falha de rede: status `erro` com `erro_mensagem = "O processamento está indisponível no momento. Tente de novo em alguns minutos."` e registrar o detalhe técnico no log da função (nunca mostrar ao usuário).
5. Incrementar `usage` só quando o motor aceitar (202).

## 2. Edge function `engine-callback`

Pública (sem JWT do Supabase), mas protegida pelo token do motor:

1. Recusar com 401 se o cabeçalho não for exatamente `Authorization: Bearer {ENGINE_CALLBACK_TOKEN}` (comparação em tempo constante).
2. Ler o JSON e tratar pelo campo `tipo`:

**`progresso`** — `{ "tipo": "progresso", "song_id", "etapa", "mensagem" }`
Atualizar `songs.etapa_atual = etapa` e zerar `posicao_fila`. Etapas possíveis, nesta ordem: `preparo`, `separacao`, `analise`, `letra`, `transcricao`, `materiais`.

**`concluido`** — `{ "tipo": "concluido", "song_id", "resultado" }`
- `songs.resultado = resultado`, `bpm = resultado.bpm`, `tom = resultado.tom.cifra`, `duracao = resultado.duracao`, `status = 'pronto'`, `etapa_atual = null`.
- Para cada par em `resultado.faixas` (ex.: `"voz": "<song_id>/voz.mp3"`), inserir em `stems` com `faixa = <nome>` e `arquivo_path = <caminho>`. Esse caminho é **dentro do bucket `stems`**. Apague antes as stems antigas da mesma música, para o callback poder ser reenviado sem duplicar.
- `resultado.arquivos` traz os caminhos **dentro do bucket `results`**: `cifra` (txt), `tablatura` (txt), `musicxml` e `midi`.
- O motor pode reenviar o mesmo resultado se não receber 200; trate como idempotente.

**`erro`** — `{ "tipo": "erro", "song_id", "mensagem" }`
`status = 'erro'`, `erro_mensagem = mensagem` (já é amigável e pode ser mostrada ao usuário). Devolver o crédito do mês em `usage`, já que a música não foi processada.

3. Responder sempre 200 rapidamente quando o token e o `song_id` forem válidos (404 se a música não existir).

## 3. Front-end

- **Tela de processamento:** adicione a etapa inicial "Na fila" (mostrada quando `etapa_atual = 'na_fila'`, com "Você é o número N da fila" se `posicao_fila > 1`) antes das seis etapas. Etapas puladas (ex.: letra desligada) aparecem com um traço em vez de check. Se o status ficar `processando` por mais de 15 minutos sem mudança de etapa, mostre "Está demorando mais que o normal" com os botões "Continuar esperando" e "Tentar de novo".
- **Estúdio:** leia as faixas da tabela `stems` e gere URLs assinadas do bucket `stems` (validade de 6 horas, renovadas automaticamente). As faixas vêm em MP3. Para a partitura, baixe `resultado.arquivos.musicxml` do bucket `results` por URL assinada e renderize com o OpenSheetMusicDisplay. Os botões de exportar MIDI e MusicXML baixam os arquivos desse bucket.
- **Avisos:** se `resultado.avisos` tiver itens, mostre-os numa faixa discreta no topo do Estúdio (fundo `#1C1C26`, texto `#B4B4C2`, ícone de informação), com botão para fechar.
- **Erro:** na biblioteca e no Estúdio, músicas com `status = 'erro'` mostram a `erro_mensagem` e o botão "Tentar de novo", que chama `process-song` outra vez com o mesmo arquivo.

## 4. Página de status do motor (só para administradores)

Crie a rota `/app/admin/motor`, visível apenas para usuários com `profiles.is_admin = true` (nova coluna boolean, padrão false). Ela chama uma nova edge function `engine-health`, que faz `GET {ENGINE_URL}/saude` e devolve o resultado. Mostre:

- se o motor está no ar (bolinha verde `#34D399` ou rosa `#F472B6`), a versão e o tamanho da fila;
- os recursos disponíveis (separação, transcrição, letra, ffmpeg, GPU), cada um com check ou X;
- as últimas 20 músicas processadas, com tempo de processamento (`resultado.tempo_total`) e status.

Ao terminar, teste o fluxo completo: envie um arquivo, acompanhe as etapas mudando na tela de processamento e confira, no Estúdio, se as faixas tocam, a cifra aparece e a partitura carrega.
