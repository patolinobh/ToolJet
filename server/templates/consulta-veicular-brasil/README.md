# Consulta Veicular Brasil

Template ToolJet para consulta completa de veículos brasileiros a partir do **chassi/VIN**
(preferencial), do **Renavam** ou da **placa** (padrão antigo ou Mercosul). A aplicação
apresenta:

- **Dados cadastrais** — marca, modelo, ano de fabricação/modelo, cor, combustível,
  placa, município/UF, procedência e código FIPE;
- **Situação legal** — indicador de roubo/furto, gravame (SNG), restrições judiciais
  (RENAJUD), débitos de IPVA/licenciamento/multas e lista de restrições registradas;
- **Sinistros** — indicador e histórico de ocorrências indenizadas por seguradoras;
- **Leilões** — indicador e histórico de passagens por leilão (leiloeiro, comitente,
  lote, condição e nota de avaliação);
- **Tabela FIPE** — valor de referência vigente, mês de referência e histórico de
  12 meses.

## Como funciona

A interface tem um único campo de busca. O tipo do identificador é detectado
automaticamente na query `executarConsulta` (Run JavaScript):

- **Chassi (VIN)** — 17 caracteres alfanuméricos, sem as letras `I`, `O` e `Q`;
- **Renavam** — 9 a 11 dígitos;
- **Placa antiga** — 3 letras + 4 dígitos (`ABC1234`, com ou sem hífen);
- **Placa Mercosul** — 3 letras + dígito + letra + 2 dígitos (`ABC1D23`).

Ao consultar um provedor real, o corpo da requisição informa o campo preenchido
(`chassi`, `renavam` ou `placa` + `padraoPlaca`), permitindo rotear para o endpoint
correto do provedor.

O orquestrador então decide entre dois modos:

### 1. Modo gratuito (padrão)

Sem nenhuma configuração, o app já entrega **dados reais gratuitos** em duas frentes:

- **Consulta por chassi** — decodificação real do VIN: tabela WMI embutida com os
  fabricantes mais comuns no Brasil/Mercosul (9BW = VW Brasil, 9BD = Fiat, 9BG =
  Chevrolet…), país de origem, ano-modelo pela 10ª posição, complementados pela
  base pública [NHTSA vPIC](https://vpic.nhtsa.dot.gov/api/) (gratuita, sem
  cadastro). Situação legal, sinistros e leilões aparecem como "não coberto na
  consulta gratuita" — nunca como falso "nada consta".
- **Aba Tabela FIPE** — avaliação oficial gratuita com seleção marca → modelo →
  ano (API pública Parallelum v1), retornando valor vigente, código FIPE e mês de
  referência.

**Consulta por placa ou Renavam** não tem fonte gratuita legítima no Brasil; nesses
casos o app roda a query `consultaDemo`, que gera um laudo **simulado e
determinístico** cobrindo cenários variados, com um banner identificando claramente
que os dados são fictícios.

### 2. Modo provedor real

As bases oficiais (Senatran/Detran, SNG, RENAJUD, seguradoras) não expõem API
pública de consulta por chassi — o acesso é feito por provedores comerciais. O
template adota uma estratégia **em duas fases**:

#### Fase 1 — APIBrasil (pago; consulta por placa)

A [APIBrasil](https://apibrasil.io) oferece a *API Placa Dados* (planos pagos por
volume de requisições), retornando dados cadastrais reais + valor FIPE a partir
da placa. Para ativar:

1. Crie uma conta em `app.apibrasil.io`, ative a **API Placa Dados** e copie o
   `BearerToken` e o `DeviceToken`;
2. Em **Workspace settings → Workspace constants**, crie:
   - Constante `CONSULTA_VEICULAR_API_URL` = `https://gateway.apibrasil.io/api/v2/vehicles/dados`;
   - Secret `APIBRASIL_BEARER_TOKEN` — valor do BearerToken;
   - Secret `APIBRASIL_DEVICE_TOKEN` — valor do DeviceToken.

Quando a URL contém `apibrasil`, o app usa automaticamente a query
`consultaApiBrasil` (adaptador dedicado). Limitações da fase: a consulta real é
**somente por placa** (chassi/Renavam exibem orientação), e os indicadores de
sinistro/leilão aparecem como "não coberto pelo provedor atual".

#### Fase 2 — agregador completo (sinistro, leilão, gravame, débitos)

Contrate um agregador B2B (Olho no Carro, Checkcred, Consultar Placa,
AvaliService etc.) e:

1. Em **Workspace settings → Workspace constants**, aponte
   `CONSULTA_VEICULAR_API_URL` para o endpoint do agregador e crie o secret
   `CONSULTA_VEICULAR_API_KEY` (enviado como `Bearer` no cabeçalho
   `Authorization`);
2. Ajuste a transformação da query `consultaProvedor` para mapear a resposta do
   provedor no contrato canônico abaixo (a transformação já cobre os apelidos de
   campo mais comuns).

Quando a constante de URL está definida, o app passa automaticamente a usar o
provedor real; caso contrário, permanece em modo demonstração.

### Valor FIPE ao vivo

Quando o provedor retorna o `codigoFipe` e o `anoModelo` do veículo, a query
`consultarFipe` busca o valor vigente na API pública da FIPE
([Parallelum](https://deividfortuna.github.io/fipe/), `fipe/api/v2`) e sobrescreve o
valor informado pelo provedor. A consulta é complementar: em caso de falha, o valor
do provedor é mantido.

## Contrato de dados canônico

Toda a interface lê a variável de página `resultado`, definida pelo orquestrador:

```jsonc
{
  "veiculo": {
    "chassi": "9BWZZZ377VT004251",
    "renavam": "12345678901",
    "placa": "BRA1C23",
    "marca": "Volkswagen",
    "modelo": "T-Cross 1.4 TSI Highline",
    "anoFabricacao": 2021,
    "anoModelo": 2022,
    "cor": "Prata",
    "combustivel": "Flex",
    "codigoCombustivel": 1,
    "municipio": "São Paulo",
    "uf": "SP",
    "codigoFipe": "005526-3",
    "procedencia": "Nacional",
    "tipo": "Automóvel",
    "situacao": "Em circulação"
  },
  "situacaoLegal": {
    "status": "Regular | Com restrições | Alerta",
    "rouboFurto": { "indicador": false, "detalhes": "Nada consta..." },
    "gravame": { "status": "Ativo", "financeira": "Banco X", "dataInclusao": "02/05/2023" },
    "debitos": { "ipva": "Sem débitos", "licenciamento": "Em dia", "multas": "R$ 293,47" },
    "renajud": "Nada consta no RENAJUD.",
    "restricoes": [{ "tipo": "...", "descricao": "...", "orgao": "..." }]
  },
  "sinistros": {
    "indicador": true,  // true | false | null (null = não coberto pelo provedor atual)
    "ocorrencias": [{ "data": "...", "tipo": "...", "gravidade": "...", "uf": "...", "descricao": "..." }]
  },
  "leiloes": {
    "indicador": true,
    "ocorrencias": [{ "data": "...", "leiloeiro": "...", "comitente": "...", "lote": "...", "condicao": "...", "notaAvaliacao": "..." }]
  },
  "fipe": {
    "codigoFipe": "005526-3",
    "valor": "R$ 128.500,00",
    "mesReferencia": "agosto de 2026",
    "historico": [{ "mes": "...", "valor": "..." }]
  },
  "metadados": { "fonte": "...", "modoDemo": false, "consultadoEm": "..." }
}
```

## Estrutura da aplicação

| Query | Tipo | Função |
| --- | --- | --- |
| `executarConsulta` | Run JavaScript | Orquestrador: valida a entrada, detecta o tipo, escolhe o modo (gratuito / APIBrasil / provedor genérico / demo), decodifica chassi (WMI local), dispara consultas e publica `variables.resultado`. |
| `decodificarVin` | REST API | Modo gratuito: `GET` na base pública NHTSA vPIC (`DecodeVinValues`) para decodificar o chassi. |
| `fipeMarcas` / `fipeModelos` / `fipeAnos` / `fipeValorSelecao` | REST API | Aba Tabela FIPE: navegação marca → modelo → ano e valor oficial vigente (API pública Parallelum v1). |
| `consultaDemo` | Run JavaScript | Gera o laudo simulado determinístico (placa/Renavam sem provedor configurado). |
| `consultaApiBrasil` | REST API | Fase 1: `POST` na APIBrasil (*API Placa Dados*) com headers `Authorization: Bearer` + `DeviceToken`; transformação normaliza para o contrato canônico. |
| `consultaProvedor` | REST API | Fase 2: `POST {{constants.CONSULTA_VEICULAR_API_URL}}` com o identificador; transformação normaliza a resposta para o contrato canônico. |
| `consultarFipe` | REST API | `GET` na API pública da FIPE por código FIPE + ano-modelo. |

Aviso legal: o aplicativo tem caráter informativo e não substitui a certidão
oficial emitida pelo Detran do estado de registro do veículo.
