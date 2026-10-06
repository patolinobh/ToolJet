# LagoaCare — banco de dados (PostgreSQL + Supabase)

Marketplace de **diaristas MEI** (CNAE 9700-5/00, serviços domésticos) para famílias do
condomínio. A plataforma conecta diaristas e famílias; o deslocamento é combinado entre
elas e pago pela família.

## Estrutura

```
supabase/migrations/0001_schema.sql   tabelas, regras de agenda (trigger) e view de faturamento
supabase/migrations/0002_acesso.sql   RLS, permissões e funções (RPC) chamadas pelo app
supabase/seed.sql                     catálogo inicial de tarefas (todas "pendente")
supabase/tests/                       shim do Supabase + testes das regras
scripts/test_db.sh                    banco descartável + migrations + testes
```

Testes (precisa de um Postgres 15+ local):

```
PG_ADMIN_URL=postgresql://postgres:senha@localhost/postgres ./scripts/test_db.sh
```

## Regras implementadas no banco

| # | Regra | Onde |
|---|---|---|
| 1 | Mesma diarista × mesma residência: no máximo 2 dias em **qualquer janela móvel de 7 dias**. Sem exceção, nem para admin. | trigger `turnos_validar` + trava por par (concorrência) |
| 2 | Pedido recusado pela diarista ou cancelado pela plataforma não conta | `turno_conta_limite` |
| 3 | Cancelamento da família com **menos de 24h** conta; com antecedência, não | `cancelamento_tardio` |
| 4 | Identidade da residência = condomínio+quadra+lote normalizados; duas contas na mesma casa dividem o contador | `residencias.chave` (única) |
| 5 | Até 8h de trabalho efetivo, pausa mínima de 1h; deslocamento fora da conta | CHECK em `turnos` |
| 6 | A diarista não tem dois turnos sobrepostos | exclusion constraint |
| 7 | Faturamento anual do MEI com alerta a 80% do teto | view `diarista_faturamento_ano` + `parametros` |

Para 7 dias/semana na mesma casa são necessárias ao menos 4 diaristas em rodízio.

## Acesso

- O cliente só **lê** o que é seu (RLS) e **escreve por funções**: `registrar_familia`,
  `registrar_diarista`, `solicitar_turno`, `responder_turno`, `cancelar_turno_familia`.
- O preço do turno vem do perfil da diarista (ela define o próprio valor).
- A diarista só aparece em `diaristas_disponiveis` depois da curadoria
  (`documentos_validados_em`, feita via service_role).
- CPF do pagador e da diarista não são legíveis pelo cliente. `parametros` é só service_role.

## Pendências (dependem de decisão externa)

- **Contador:** confirmar o enquadramento de cada tarefa na ocupação MEI. Em especial
  *cuidado infantil*. Tudo está `pendente` em `catalogo_tarefas.enquadramento`.
- **Teto do MEI:** conferir o valor vigente (`parametros.teto_mei_anual_centavos`).
- **Advogado:** definir "semana" (hoje: janela móvel de 7 dias), tratamento do auxílio de
  deslocamento e o desenho de transporte por indicação.
- **CEP/condomínio:** a restrição à região do piloto ainda não está no banco.
- **Próximas funções:** check-in na portaria, "estou a caminho", pausa, checklist e avaliação.
