#!/usr/bin/env bash
# Aplica as migrations em um banco descartável e roda os testes.
# Uso: PG_ADMIN_URL=postgresql://postgres@localhost/postgres ./scripts/test_db.sh
set -euo pipefail
cd "$(dirname "$0")/.."

ADMIN_URL="${PG_ADMIN_URL:-postgresql://postgres@localhost/postgres}"
DB="lagoacare_test"
TEST_URL="${ADMIN_URL%/*}/$DB"

psql "$ADMIN_URL" -v ON_ERROR_STOP=1 -q -c "drop database if exists $DB" -c "create database $DB"
trap 'psql "$ADMIN_URL" -q -c "drop database if exists $DB" >/dev/null' EXIT

run() { psql "$TEST_URL" -v ON_ERROR_STOP=1 -q "$@"; }

run -f supabase/tests/00_shim_supabase.sql
for f in supabase/migrations/*.sql; do run -f "$f"; done
run -f supabase/seed.sql
run -f supabase/tests/regras.test.sql

# Concorrência: duas sessões tentam, ao mesmo tempo, ocupar o 2º e o 3º dia de uma
# mesma janela. A trava por par (diarista, residência) deve deixar passar só uma.
run <<'SQL'
insert into auth.users (id) values ('00000000-0000-0000-0000-0000000000a9'), ('00000000-0000-0000-0000-0000000000d9');
insert into public.perfis (id, papel, nome) values
  ('00000000-0000-0000-0000-0000000000a9', 'familia', 'F'), ('00000000-0000-0000-0000-0000000000d9', 'diarista', 'D');
insert into public.residencias (id, condominio, quadra, lote, cep) values ('00000000-0000-0000-0000-00000000aa09', 'X', 'X', '9', '34000000');
insert into public.familias (id, perfil_id, residencia_id, nome_responsavel, cpf_pagador)
  values ('00000000-0000-0000-0000-00000000f009', '00000000-0000-0000-0000-0000000000a9', '00000000-0000-0000-0000-00000000aa09', 'F', '99999999999');
insert into public.diaristas (id, perfil_id, cpf, cnpj) values
  ('00000000-0000-0000-0000-00000000d009', '00000000-0000-0000-0000-0000000000d9', '99999999990', '90000000000009');
insert into public.turnos (diarista_id, residencia_id, familia_id, data, hora_inicio, hora_fim, valor_diaria_centavos)
  values ('00000000-0000-0000-0000-00000000d009', '00000000-0000-0000-0000-00000000aa09', '00000000-0000-0000-0000-00000000f009', date '2031-03-03', '08:00', '17:00', 20000);
SQL

ins() {  # $1 = data, $2 = segundos de atraso antes do commit
  psql "$TEST_URL" -v ON_ERROR_STOP=1 -q -c "begin;
    insert into public.turnos (diarista_id, residencia_id, familia_id, data, hora_inicio, hora_fim, valor_diaria_centavos)
    values ('00000000-0000-0000-0000-00000000d009', '00000000-0000-0000-0000-00000000aa09', '00000000-0000-0000-0000-00000000f009', date '$1', '08:00', '17:00', 20000);
    select pg_sleep($2); commit;" >/dev/null 2>&1
}
ins 2031-03-05 2 || true &
sleep 0.5
ins 2031-03-07 0 || true &
wait
n=$(run -At -c "select count(distinct data) from public.turnos where diarista_id = '00000000-0000-0000-0000-00000000d009'")
if [ "$n" -ne 2 ]; then echo "FALHA concorrência: esperava 2 dias, há $n"; exit 1; fi
echo "ok: concorrência (2 dias, a 3ª gravação simultânea foi barrada)"
echo "TODOS OS TESTES PASSARAM"
