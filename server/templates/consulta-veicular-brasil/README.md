# Consulta Veicular Brasil

Template ToolJet para consulta completa de veículos brasileiros a partir do **chassi**
(preferencial) ou do **Renavam**. A aplicação apresenta:

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
- **Renavam** — 9 a 11 dígitos.

O orquestrador então decide entre dois modos:

### 1. Modo demonstração (padrão)

Sem nenhuma configuração, o app roda com a query `consultaDemo`, que gera um laudo
**simulado e determinístico** (o mesmo identificador sempre produz o mesmo
resultado), cobrindo cenários variados: veículo regular, com gravame, com restrição
judicial, com sinistro, com leilão e com ocorrência de roubo/furto. Um banner
identifica claramente que os dados são fictícios.

### 2. Modo provedor real

As bases oficiais (Senatran/Detran, SNG, RENAJUD, seguradoras) não expõem API
pública de consulta por chassi — o acesso é feito por provedores comerciais, como
Infosimples, API Brasil, Checkpro ou Olho no Carro. Para conectar o seu:

1. Em **Workspace settings → Workspace constants**, crie:
   - Constante `CONSULTA_VEICULAR_API_URL` — URL do endpoint de consulta do provedor;
   - Secret `CONSULTA_VEICULAR_API_KEY` — chave de API (enviada como `Bearer` no
     cabeçalho `Authorization`).
2. Ajuste a transformação da query `consultaProvedor` para mapear a resposta do seu
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
    "indicador": true,
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
| `executarConsulta` | Run JavaScript | Orquestrador: valida a entrada, detecta chassi/Renavam, escolhe o modo, dispara a consulta FIPE e publica `variables.resultado`. |
| `consultaDemo` | Run JavaScript | Gera o laudo simulado determinístico (modo demonstração). |
| `consultaProvedor` | REST API | `POST {{constants.CONSULTA_VEICULAR_API_URL}}` com o identificador; transformação normaliza a resposta para o contrato canônico. |
| `consultarFipe` | REST API | `GET` na API pública da FIPE por código FIPE + ano-modelo. |

Aviso legal: o aplicativo tem caráter informativo e não substitui a certidão
oficial emitida pelo Detran do estado de registro do veículo.
