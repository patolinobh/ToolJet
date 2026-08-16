# Vehicle History MVP - ToolJet integration

Este repositório contém o scaffold inicial do backend (FastAPI) para o MVP de consulta de histórico veicular.

Rodando localmente

1. Copie o arquivo de exemplo de ambiente:

   cp .env.example .env

2. Ajuste variáveis se necessário (não adicione chaves em commits).

3. Inicie via docker-compose:

   docker compose up --build

A API ficará disponível em http://localhost:8000

Endpoints principais

- GET /health - verificação de integridade
- POST /lookup - consulta por VIN ou RENAVAM

ToolJet

Instruções para integrar com ToolJet estão em docs/tooljet-integration.md
