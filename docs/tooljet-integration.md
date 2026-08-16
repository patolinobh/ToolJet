# ToolJet integration guide

1) No ToolJet, crie uma nova página (ex: "Consulta Veicular").
2) Adicione um campo de texto para inserir VIN ou RENAVAM.
3) Crie um botão que dispara uma HTTP action:
   - Método: POST
   - URL: https://<sua-url>/api/v1/lookup
   - Headers: Authorization: Bearer <TOKEN_SEU>
   - Body (JSON): { "identifier": {{text_input.value}}, "type": "vin" }
4) Mapeie a resposta para widgets (painéis, tabelas). Use condicionais para exibir valuation/decoded.
5) Configure secrets no ToolJet para HOST/TOKEN e não exponha chaves públicas.

