# Prompt para o Lovable: braço animado no estúdio

Copie tudo abaixo da linha e cole no Lovable, no mesmo projeto do Prismo.

---

Adicione ao Estúdio do Prismo o recurso **"braço animado"**: um braço de violão/guitarra desenhado por código que mostra, sincronizado com a música, onde cada dedo fica no acorde que está tocando, com os dedos deslizando até a posição do próximo acorde. É para quem aprende melhor vendo do que lendo diagramas. Mantenha toda a identidade visual atual (fundo `#0A0A0F`, cartões `#12121A`, bordas `#23232F`, Space Grotesk, Inter, JetBrains Mono) e não altere o que já funciona nas outras telas.

**Importante:** nada aqui usa imagem ou vídeo gerado por IA. Tudo é desenhado em SVG ou HTML a partir dos dados do acorde, para ser sempre exato, funcionar em qualquer tom e ter custo zero.

## 1. Onde aparece

No seletor de material do Estúdio, troque "Cifra" por **"Cifra + braço"** (mantenha "Tablatura" e "Partitura"). Nesse modo, o layout fica:

- **Desktop:** duas colunas. À esquerda (cerca de 400px), a cifra com letra, rolando sozinha e com a linha atual destacada (fundo `#1C1C26`, texto `#F4F4F7`; as outras linhas em `#8A8A9A`). À direita, o painel do braço.
- **Celular:** o braço fica fixo no topo (altura menor, com rolagem horizontal do braço se precisar) e a cifra rola embaixo.
- Um botão "Ocultar braço" volta para a cifra em tela cheia. A escolha fica salva nas preferências do usuário.

## 2. O painel do braço

Dentro de um cartão `surface` com raio 20px, de cima para baixo:

1. **Cabeçalho:** nome do acorde atual grande (Space Grotesk 64px, peso 500, letter-spacing -2px) e o nome por extenso ao lado em `#B4B4C2` ("Mi menor", "Dó maior", "Ré com sétima"). À direita, dois botões de alternância (borda `#2A2A36`; quando ativos, fundo `#2E2A44` e borda `#8B5CF6`):
   - **Canhoto:** espelha o braço horizontalmente.
   - **Mostrando dedos / Mostrando notas:** troca o número do dedo pelo nome da nota que soa naquela casa.
2. **O braço** (componente `<Fretboard />`, SVG ou divs posicionadas, responsivo pela largura):
   - madeira do braço em `#1A1410` com cantos arredondados;
   - pestana (nut) em `#E8E2D4`, ou, quando há capotraste sugerido, uma barra roxa `#8B5CF6` atravessando todas as cordas na casa do capo, com o rótulo "Capo 2";
   - 5 casas visíveis por padrão (a janela acompanha acordes mais altos, mostrando o número da primeira casa ao lado, ex.: "5ª"), trastes em `#6B6B7B` e marcações (bolinhas `#2E2620`) nas casas 3, 5, 7, 9 e dupla na 12;
   - 6 cordas em `#C9C3B6`, com espessura decrescente da mais grave para a mais aguda; **a corda mais aguda (e) em cima e a mais grave (E) embaixo**, igual à tablatura; rótulos E A D G B e na lateral, em mono `#8A8A9A`;
   - números das casas embaixo, em mono 12px;
   - antes da pestana, em cada corda: **O** verde `#34D399` para corda solta e **X** rosa `#F472B6` para corda que não deve soar;
   - **dedos:** círculos de 44px em `#A78BFA` com o número do dedo (1 indicador, 2 médio, 3 anelar, 4 mínimo) em `#0A0A0F`, peso 600; **pestana (barre)** desenhada como uma cápsula roxa atravessando as cordas, com o número 1.
3. **Batida (ritmo):** uma linha com 8 quadrados (colcheias de um compasso 4/4), cada um com uma seta para baixo (cor `#C4B5FD`) ou para cima (cor `#F9A8D4`) ou vazio (pausa). O quadrado da colcheia atual acende (fundo `#2E2A44`, borda `#8B5CF6`, leve aumento de escala). O padrão padrão é "baixo, baixo, pausa, cima, cima, baixo, cima, pausa", escrito ao lado em mono. O usuário pode escolher outros padrões num menu (Pop/rock, Balada, Reggae, Sertanejo, Louvor) ou clicar nos quadrados para montar o próprio. O padrão fica salvo por música.
4. **Cartões de acordes da música:** uma fileira com os acordes usados na música, na ordem em que aparecem pela primeira vez (Space Grotesk 28px, cartão de 92px de altura). O acorde tocando agora tem borda 2px `#8B5CF6` e o texto "tocando agora"; os outros mostram "tocar este". Clicar num cartão pausa a música e mostra aquele acorde no braço, para estudar com calma. No fim da fileira, um cartão de borda tracejada com **"Próximo acorde"** e o nome dele em `#C4B5FD`.

## 3. Animação (o coração do recurso)

- Os 4 dedos são **sempre os mesmos elementos** (dedo 1, 2, 3 e 4), e a posição deles muda de acorde para acorde. Assim, na troca, cada dedo **desliza** da posição antiga para a nova (transição de 420 ms, `cubic-bezier(.3,.7,.2,1)`), e o aluno vê qual dedo se move e qual fica parado (ex.: de Em para C, o dedo 2 fica na mesma casa e só muda de corda). Dedos que não são usados no novo acorde encolhem e somem (escala 0.4 e opacidade 0); dedos que entram aparecem crescendo.
- **Antecipação:** meio tempo antes da troca, mostre o próximo acorde como "fantasmas" (círculos só com contorno `#A78BFA` a 50% de opacidade) nas posições de destino, para o aluno preparar a mão.
- Os indicadores O e X fazem transição de cor suave.
- Tudo sincronizado com o player do Estúdio: usa o tempo atual da reprodução e os tempos de `resultado.acordes` (`inicio`, `fim`) para saber o acorde atual e o próximo; a batida usa o `bpm` e `resultado.batidas`. Pausar a música congela o braço. Ao mudar a velocidade (0.5x, 0.75x), a animação acompanha.
- Respeite `prefers-reduced-motion`: sem deslizamento, só troca direta.
- Quando a transposição de tom ou o capotraste mudam, o braço atualiza na hora.

## 4. Biblioteca de formas de acorde (`src/lib/music/voicings.ts`)

Crie uma biblioteca com o formato:

```ts
type Corda = 0 | 1 | 2 | 3 | 4 | 5; // 0 = E grave, 5 = e agudo
type Posicao = { corda: Corda; casa: number; dedo: 0 | 1 | 2 | 3 | 4 }; // casa -1 = não tocar, 0 = solta
type Forma = { nome: string; posicoes: Posicao[]; pestana?: { casa: number; deCorda: Corda; ateCorda: Corda } };
```

Formas abertas que devem existir exatamente assim (casa por corda, de E grave a e agudo; x = não tocar; dedo entre parênteses):

| Acorde | E | A | D | G | B | e |
|---|---|---|---|---|---|---|
| C | x | 3(3) | 2(2) | 0 | 1(1) | 0 |
| D | x | x | 0 | 2(1) | 3(3) | 2(2) |
| E | 0 | 2(2) | 2(3) | 1(1) | 0 | 0 |
| G | 3(2) | 2(1) | 0 | 0 | 0 | 3(3) |
| A | x | 0 | 2(1) | 2(2) | 2(3) | 0 |
| Am | x | 0 | 2(2) | 2(3) | 1(1) | 0 |
| Em | 0 | 2(2) | 2(3) | 0 | 0 | 0 |
| Dm | x | x | 0 | 2(2) | 3(3) | 1(1) |
| A7 | x | 0 | 2(2) | 0 | 2(3) | 0 |
| B7 | x | 2(2) | 1(1) | 2(3) | 0 | 2(4) |
| C7 | x | 3(3) | 2(2) | 3(4) | 1(1) | 0 |
| D7 | x | x | 0 | 2(2) | 1(1) | 2(3) |
| E7 | 0 | 2(2) | 0 | 1(1) | 0 | 0 |
| G7 | 3(3) | 2(2) | 0 | 0 | 0 | 1(1) |
| Am7 | x | 0 | 2(2) | 0 | 1(1) | 0 |
| Em7 | 0 | 2(2) | 0 | 0 | 0 | 0 |
| Dm7 | x | x | 0 | 2(2) | 1(1) | 1(1) |
| C7M | x | 3(3) | 2(2) | 0 | 0 | 0 |
| D7M | x | x | 0 | 2(1) | 2(2) | 2(3) |
| F7M | x | x | 3(3) | 2(2) | 1(1) | 0 |
| G7M | 3(3) | 2(2) | 0 | 0 | 0 | 2(1) |
| A7M | x | 0 | 2(2) | 1(1) | 2(3) | 0 |

Para os outros acordes, gere **formas com pestana móveis**, escolhendo a de casa mais baixa:

- **Forma de E (raiz na 6ª corda):** maior `[0,2,2,1,0,0]`, menor `[0,2,2,0,0,0]`, 7 `[0,2,0,1,0,0]`, m7 `[0,2,0,0,0,0]`, 7M `[0,x,1,1,0,x]`, deslocadas pela casa da raiz, com a pestana do dedo 1 na casa da raiz.
- **Forma de A (raiz na 5ª corda):** maior `[x,0,2,2,2,0]`, menor `[x,0,2,2,1,0]`, 7 `[x,0,2,0,2,0]`, m7 `[x,0,2,0,1,0]`, 7M `[x,0,2,1,2,0]`, com a mesma lógica.
- Distribua os dedos 2, 3 e 4 nas casas acima da pestana, do grave para o agudo, como um violonista faria (ex.: F = pestana na 1ª, dedo 3 na A3, dedo 4 na D3, dedo 2 na G2).
- Diminuto (°): forma `[x,x,0,1,0,1]` relativa a D, móvel.
- Acorde com baixo (ex.: D/F#): use a forma do acorde e acrescente o baixo na 6ª ou 5ª corda, se couber na mão; senão, mostre a forma sem o baixo e uma nota "baixo em F#".
- Quando houver capotraste, mostre a forma relativa ao capo (com capo 2, F#m aparece como a forma de Em).
- O usuário pode trocar a forma de um acorde (botão "Outra posição" no cabeçalho do painel), percorrendo as formas disponíveis; a escolha fica salva por música em `song_edits`.

Escreva testes unitários para a biblioteca: todas as formas da tabela têm as notas certas do acorde (usando a afinação E2 A2 D3 G3 B3 E4), a transposição gera a forma esperada (ex.: F# maior = pestana na 2ª casa) e o espelhamento para canhoto inverte apenas a posição horizontal.

## 5. Modo baixo

Se o instrumento da música for baixo, o braço mostra 4 cordas (G D A E) e, em vez da forma do acorde, destaca a **nota fundamental** de cada acorde na posição mais próxima da anterior, com a nota do baixo invertido quando houver (D/F# mostra F#). As bolinhas ficam em azul `#60A5FA`.

## 6. Preferências e acessibilidade

- Em Configurações, nova seção "Braço animado": canhoto (salvo no perfil), mostrar dedos ou notas, mostrar antecipação do próximo acorde, padrão de batida preferido.
- O braço tem `role="img"` e `aria-label` descrevendo o acorde ("Mi menor: dedo 2 na corda Lá, casa 2; dedo 3 na corda Ré, casa 2; as outras cordas soltas").
- Atalhos de teclado: barra de espaço toca/pausa, setas esquerda e direita vão para o acorde anterior ou o próximo, L alterna canhoto.
- A música de exemplo da biblioteca ("Exemplo: Toca de novo") deve abrir já no modo "Cifra + braço", para o usuário novo ver o recurso logo de cara.

## 7. Landing page

Na seção de recursos, acrescente um terceiro bloco: rótulo "PARA QUEM APRENDE VENDO", título "Veja onde cada dedo vai, no ritmo da música.", um texto curto e uma versão compacta do braço animado em loop com Em, C, G e D (dedos deslizando entre os acordes), sem controles.

Ao terminar, abra o Estúdio da música de exemplo e confira: dedos deslizando na troca de acorde, batida acendendo no ritmo, cifra destacando a linha atual, modo canhoto espelhando e o modo notas mostrando os nomes corretos.
