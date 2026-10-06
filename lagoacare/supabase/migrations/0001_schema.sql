-- LagoaCare: esquema base (diaristas MEI, CNAE 9700-5/00) e regras de agenda.
-- Convenções: nomes em português, snake_case, valores monetários em centavos.

create extension if not exists btree_gist;

-- ---------------------------------------------------------------------------
-- Identidade
-- ---------------------------------------------------------------------------

create table public.perfis (
  id         uuid primary key references auth.users (id) on delete cascade,
  papel      text not null check (papel in ('familia', 'diarista', 'admin')),
  nome       text not null,
  telefone   text,
  criado_em  timestamptz not null default now()
);

-- Uma residência é única por (condomínio, quadra, lote) normalizados. Duas contas
-- de família na mesma casa apontam para a mesma linha e, portanto, dividem o
-- contador da Regra 1 (limite de 2 dias por diarista).
create table public.residencias (
  id          uuid primary key default gen_random_uuid(),
  condominio  text not null,
  quadra      text not null,
  lote        text not null,
  cep         text not null check (cep ~ '^[0-9]{8}$'),
  logradouro  text,
  chave       text generated always as (
                lower(btrim(condominio)) || '|' || lower(btrim(quadra)) || '|' || lower(btrim(lote))
              ) stored,
  criado_em   timestamptz not null default now(),
  constraint residencias_chave_key unique (chave)
);

create table public.familias (
  id                uuid primary key default gen_random_uuid(),
  perfil_id         uuid not null unique references public.perfis (id) on delete cascade,
  residencia_id     uuid not null references public.residencias (id),
  nome_responsavel  text not null,
  cpf_pagador       text not null check (cpf_pagador ~ '^[0-9]{11}$'),
  criado_em         timestamptz not null default now(),
  unique (cpf_pagador, residencia_id),
  unique (id, residencia_id)  -- alvo da FK composta de turnos
);

create table public.diaristas (
  id                        uuid primary key default gen_random_uuid(),
  perfil_id                 uuid not null unique references public.perfis (id) on delete cascade,
  cpf                       text not null unique check (cpf ~ '^[0-9]{11}$'),
  regime                    text not null default 'mei' check (regime in ('mei', 'autonoma_pf')),
  cnpj                      text unique check (cnpj ~ '^[0-9]{14}$'),
  cnae                      text not null default '9700500',
  valor_diaria_centavos     integer check (valor_diaria_centavos > 0),  -- a diarista define o próprio preço
  ativo                     boolean not null default true,
  documentos_validados_em   timestamptz,                                -- curadoria da plataforma
  criado_em                 timestamptz not null default now(),
  constraint diaristas_mei_exige_cnpj check (regime <> 'mei' or cnpj is not null)
);

-- ---------------------------------------------------------------------------
-- Catálogo de tarefas
-- ---------------------------------------------------------------------------

-- enquadramento = situação da tarefa frente à ocupação do MEI. Tudo nasce
-- 'pendente' até o contador confirmar (cuidado infantil é o caso mais incerto).
create table public.catalogo_tarefas (
  id            uuid primary key default gen_random_uuid(),
  codigo        text not null unique,
  nome          text not null,
  categoria     text not null,
  enquadramento text not null default 'pendente' check (enquadramento in ('confirmado', 'pendente'))
);

create table public.diarista_tarefas (
  diarista_id uuid not null references public.diaristas (id) on delete cascade,
  tarefa_id   uuid not null references public.catalogo_tarefas (id),
  primary key (diarista_id, tarefa_id)
);

-- Parâmetros de negócio editáveis sem deploy (somente service_role).
create table public.parametros (
  chave  text primary key,
  valor  numeric not null
);

insert into public.parametros (chave, valor) values
  ('teto_mei_anual_centavos', 8100000),  -- R$ 81.000; conferir o valor vigente
  ('alerta_teto_percentual', 80);

-- ---------------------------------------------------------------------------
-- Turnos
-- ---------------------------------------------------------------------------

-- Status que contam para a Regra 1: ocupam a agenda OU foram cancelados pela
-- família com menos de 24h de antecedência (cancelamento_tardio).
create function public.turno_conta_limite(p_status text, p_tardio boolean)
returns boolean
language sql
immutable
as $$
  select p_status in ('solicitado', 'confirmado', 'em_andamento', 'concluido')
      or (p_status = 'cancelado_familia' and p_tardio);
$$;

create table public.turnos (
  id                  uuid primary key default gen_random_uuid(),
  residencia_id       uuid not null,
  familia_id          uuid not null,
  diarista_id         uuid not null references public.diaristas (id),

  -- Planejado (horário local de Nova Lima; chegada à portaria até a saída)
  data                date not null,
  hora_inicio         time not null,
  hora_fim            time not null,
  pausa_minutos       integer not null default 60,

  -- Realizado
  a_caminho_em        timestamptz,
  chegada_em          timestamptz,
  pausa_inicio_em     timestamptz,
  pausa_fim_em        timestamptz,
  saida_em            timestamptz,

  status              text not null default 'solicitado' check (status in (
                        'solicitado', 'confirmado', 'em_andamento', 'concluido',
                        'cancelado_familia', 'cancelado_plataforma',
                        'recusado_diarista', 'falta_diarista')),
  cancelado_em        timestamptz,
  cancelamento_tardio boolean not null default false,

  valor_diaria_centavos       integer not null check (valor_diaria_centavos > 0),
  deslocamento_modo           text check (deslocamento_modo in (
                                'app_mobilidade', 'fretamento', 'transporte_publico', 'proprio')),
  deslocamento_custo_centavos integer not null default 0 check (deslocamento_custo_centavos >= 0),
  autorizacao_portaria        text not null default 'pendente'
                                check (autorizacao_portaria in ('pendente', 'liberada')),

  criado_em           timestamptz not null default now(),

  -- Derivados
  trabalho_previsto_min integer generated always as (
    (extract(epoch from (hora_fim - hora_inicio)) / 60)::integer - pausa_minutos
  ) stored,
  janela              tsrange generated always as (
    tsrange(data + hora_inicio, data + hora_fim)
  ) stored,
  conta_para_limite   boolean generated always as (
    public.turno_conta_limite(status, cancelamento_tardio)
  ) stored,

  -- A residência da família precisa ser a do turno
  constraint turnos_familia_residencia_fk
    foreign key (familia_id, residencia_id) references public.familias (id, residencia_id),

  -- Jornada: até 8h de trabalho efetivo, pausa mínima de 1h; deslocamento fora da conta
  constraint turnos_horario_valido    check (hora_fim > hora_inicio),
  constraint turnos_pausa_minima      check (pausa_minutos >= 60),
  constraint turnos_trabalho_maximo   check (
    (extract(epoch from (hora_fim - hora_inicio)) / 60)::integer - pausa_minutos between 1 and 480),

  -- A diarista não pode ter dois turnos sobrepostos
  constraint turnos_sem_sobreposicao exclude using gist (
    diarista_id with =, janela with &&
  ) where (status in ('solicitado', 'confirmado', 'em_andamento', 'concluido'))
);

create index turnos_par_data_idx on public.turnos (diarista_id, residencia_id, data)
  where conta_para_limite;
create index turnos_residencia_data_idx on public.turnos (residencia_id, data);

create table public.turno_tarefas (
  turno_id   uuid not null references public.turnos (id) on delete cascade,
  tarefa_id  uuid not null references public.catalogo_tarefas (id),
  concluida  boolean not null default false,
  foto_url   text,
  primary key (turno_id, tarefa_id)
);

-- ---------------------------------------------------------------------------
-- Regra 1: mesma diarista x mesma residência, no máximo 2 dias em QUALQUER
-- janela móvel de 7 dias consecutivos. Bloqueio no banco, sem exceção.
-- ---------------------------------------------------------------------------

create function public.turnos_validar()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  i integer;
  s date;
  n integer;
begin
  -- Cancelamento pela família: registra o instante e se foi tardio (< 24h)
  if new.status = 'cancelado_familia'
     and (tg_op = 'INSERT' or old.status is distinct from new.status) then
    new.cancelado_em := now();
    new.cancelamento_tardio :=
      (now() at time zone 'America/Sao_Paulo') > (new.data + new.hora_inicio - interval '24 hours');
  end if;

  if not public.turno_conta_limite(new.status, new.cancelamento_tardio) then
    return new;
  end if;

  -- Nada relevante mudou: a regra já foi validada na gravação anterior
  if tg_op = 'UPDATE'
     and old.diarista_id = new.diarista_id
     and old.residencia_id = new.residencia_id
     and old.data = new.data
     and public.turno_conta_limite(old.status, old.cancelamento_tardio) then
    return new;
  end if;

  -- Serializa gravações concorrentes do mesmo par (diarista, residência)
  perform pg_advisory_xact_lock(
    hashtextextended(new.diarista_id::text || '|' || new.residencia_id::text, 0));

  -- Cada janela [s, s+6] que contém a data nova não pode passar de 2 dias distintos
  for i in 0..6 loop
    s := new.data - i;
    select count(*) into n from (
      select t.data
        from public.turnos t
       where t.diarista_id   = new.diarista_id
         and t.residencia_id = new.residencia_id
         and t.conta_para_limite
         and t.id <> new.id
         and t.data between s and s + 6
      union
      select new.data
    ) dias;

    if n > 2 then
      raise exception 'limite_diarista_residencia'
        using errcode = 'check_violation',
              detail  = format('A diarista já atende esta residência em 2 dias na janela %s a %s.',
                               s, s + 6),
              hint    = 'Escolha outra data ou outra diarista (rodízio).';
    end if;
  end loop;

  return new;
end;
$$;

create trigger turnos_validar
  before insert or update on public.turnos
  for each row execute function public.turnos_validar();

-- ---------------------------------------------------------------------------
-- Regra 6: faturamento anual do MEI frente ao teto (diárias concluídas;
-- reembolso de deslocamento não entra, pois é repasse da família).
-- ---------------------------------------------------------------------------

create view public.diarista_faturamento_ano
with (security_invoker = true) as
select
  t.diarista_id,
  extract(year from t.data)::integer                                   as ano,
  sum(t.valor_diaria_centavos)::bigint                                 as faturado_centavos,
  round(100.0 * sum(t.valor_diaria_centavos)
        / (select valor from public.parametros where chave = 'teto_mei_anual_centavos'), 1)
                                                                       as percentual_teto,
  (100.0 * sum(t.valor_diaria_centavos)
        / (select valor from public.parametros where chave = 'teto_mei_anual_centavos')
   ) >= (select valor from public.parametros where chave = 'alerta_teto_percentual')
                                                                       as alerta_teto
from public.turnos t
where t.status = 'concluido'
group by t.diarista_id, extract(year from t.data);
