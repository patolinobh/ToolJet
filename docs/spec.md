# Especificação mínima - Vehicle History API (MVP)

Endpoints

- GET /health
  - Retorno: {"status":"ok"}

- POST /api/v1/lookup
  - Payload: { "identifier": "<vin|renavam>", "type": "vin"|"renavam" }
  - Validação:
    - VIN: 17 caracteres alfanuméricos (exclui I,O,Q)
    - RENAVAM: 9-11 dígitos (validação adicional futura)
  - Resposta (resumida):
    - identifier, type, decoded (se VIN), valuation (FIPE se disponível), claims[], auctions[]

Modelos de dados

- Vehicle: vin, renavam, make, model, year
- Valuation: fonte, valor, moeda, data
- Claim: source, date, type, description
- Auction: source, lot_id, date, link, estimated_value

Cache

- TTL configurável via env (CACHE_TTL). Cache por identifier e type.

Erros comuns

- 422: request inválido
- 502/503: provedores externos indisponíveis — retorno parcial com chave de erro em valuation/claims

LGPD e privacidade

- Não armazenar chaves/credenciais no repositório.
- Considerar consentimento do titular para consultas via RENAVAM.
- Redaction: por default mascarar VIN/RENAVAM quando enviado a provedores externos.
