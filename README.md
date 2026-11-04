# Prismo

Plataforma para músicos: envie um áudio ou vídeo e receba cada instrumento separado, com cifra, tablatura e partitura prontas para tocar.

> Um prisma separa a luz em cores. O Prismo separa a música em instrumentos.

## Estrutura

```
prismo/
├── engine/   Motor de áudio em Python (separação, transcrição, acordes)
├── api/      API em FastAPI que recebe uploads e processa músicas (em breve)
├── web/      Site em Next.js com a identidade do Prismo (em breve)
└── docs/     Decisões de produto e de arquitetura
```

## Status

Fase atual: **prova técnica** do motor de áudio, para medir a qualidade real da separação e da transcrição antes de construir o produto.
