# Colocar o motor no ar (Modal)

O motor roda no [Modal](https://modal.com): uma GPU NVIDIA L4 liga quando chega uma música e desliga sozinha logo depois. Paga-se só pelos segundos de uso, e o plano Starter tem US$ 30 por mês em créditos grátis.

Como funciona:

```
Site (Lovable) ──POST /processar──► api (Modal, sem GPU, responde na hora)
                                     │  dispara
                                     ▼
                               processar_musica (Modal, GPU L4)
                                     │  envia faixas e arquivos pelos links assinados do site
                                     ▼
Site ◄──── callback (progresso, concluido, erro)
```

O motor **não precisa de nenhuma chave do Supabase**: a cada música, o site gera links de envio que valem só para aqueles arquivos, por 2 horas.

## Passo a passo

### 1. Conta e token no Modal

1. Crie a conta em https://modal.com (dá para entrar com o GitHub).
2. No painel, vá em **Settings → API Tokens** e clique em **New Token**.
3. Guarde o **Token ID** (começa com `ak-`) e o **Token Secret** (começa com `as-`). O secret só aparece uma vez.

### 2. Segredos do motor no Modal

No painel do Modal, vá em **Secrets → Create new secret → Custom** e crie um secret com o nome **`prismo-engine`** e estas chaves:

| Chave | Valor |
|---|---|
| `PRISMO_TOKEN` | a senha que o site usa para chamar o motor (longa e aleatória) |
| `PRISMO_CALLBACK_TOKEN` | a senha que o motor usa para avisar o site (outra, longa e aleatória) |
| `SUPABASE_URL` | o endereço do Supabase do projeto, `https://<id>.supabase.co` (no Lovable: `.env`, `VITE_SUPABASE_URL`) |
| `PRISMO_HOSTS_CALLBACK` | o domínio do site publicado, sem `https://` (ex.: `prismo-song-scribe.lovable.app`). Se tiver mais de um, separe por vírgula |

### 3. Token do Modal no GitHub

No repositório `akaLouiz/prismo` no GitHub: **Settings → Secrets and variables → Actions → New repository secret**. Crie dois:

- `MODAL_TOKEN_ID`: o Token ID do passo 1
- `MODAL_TOKEN_SECRET`: o Token Secret do passo 1

### 4. Publicar

No GitHub, aba **Actions → Publicar motor no Modal → Run workflow**. A automação roda os testes e publica. A primeira vez leva uns 10 minutos, porque monta a imagem com os modelos de IA. Depois disso, cada atualização na pasta `engine/` publica sozinha.

No fim, o Modal mostra o endereço da API, no formato `https://<seu-usuario>--prismo-engine-api.modal.run`. Teste abrindo `<endereço>/saude` no navegador: deve aparecer `"ok": true` e `"gpu": false` (a API roda sem GPU; a GPU liga só no processamento).

### 5. Ligar o site ao motor

No Lovable, em **Settings → Secrets** (segredos do projeto), adicione:

| Segredo | Valor |
|---|---|
| `ENGINE_URL` | o endereço da API do passo 4, sem barra no final |
| `ENGINE_TOKEN` | o mesmo valor de `PRISMO_TOKEN` |
| `ENGINE_CALLBACK_TOKEN` | o mesmo valor de `PRISMO_CALLBACK_TOKEN` |
| `PUBLIC_APP_URL` | o endereço do site publicado, com `https://` (ex.: `https://prismo-song-scribe.lovable.app`) |

A partir daí o site sai do modo demonstração e processa de verdade.

## Custos e limites

- GPU L4: US$ 0,000222 por segundo. Uma música de 4 minutos deve usar entre 1 e 2 minutos de GPU (estimativa; o tempo real aparece em `resultado.tempo_total`).
- No máximo 5 GPUs ao mesmo tempo (`max_containers=5` em `modal_app.py`); músicas além disso esperam na fila do Modal.
- Cada música tem até 20 minutos para terminar.
- Para não ter surpresa, configure um limite de gasto no painel do Modal (**Settings → Usage and billing**).

## Problemas comuns

- **`/saude` não abre:** confira se a automação terminou sem erro na aba Actions.
- **Música fica em "Na fila" para sempre:** confira `PRISMO_HOSTS_CALLBACK` (o domínio do site) e `PUBLIC_APP_URL`. Os registros ficam no painel do Modal, em **Apps → prismo-engine → Logs**.
- **Erro "O processamento está indisponível":** o site não conseguiu falar com o motor. Confira `ENGINE_URL` e se `ENGINE_TOKEN` é igual a `PRISMO_TOKEN`.
