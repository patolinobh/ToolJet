-- LagoaCare: RLS, permissões e funções de aplicação (RPC).
-- Princípio: o cliente (anon/authenticated) só LÊ o que é seu e ESCREVE por
-- funções que validam o papel do usuário. Tabelas sem política ficam fechadas.

-- ---------------------------------------------------------------------------
-- Permissões básicas: o Supabase concede tudo por padrão; aqui fechamos.
-- ---------------------------------------------------------------------------

revoke all on all tables in schema public from anon, authenticated;

-- Views criadas daqui em diante nascem fechadas; cada uma recebe só os grants abaixo.
-- (Funções: o PUBLIC recebe EXECUTE por padrão e isso não se desfaz por schema;
-- por isso há um revoke explícito no final do arquivo.)
alter default privileges in schema public revoke all on tables from anon, authenticated;

alter table public.perfis            enable row level security;
alter table public.residencias       enable row level security;
alter table public.familias          enable row level security;
alter table public.diaristas         enable row level security;
alter table public.catalogo_tarefas  enable row level security;
alter table public.diarista_tarefas  enable row level security;
alter table public.parametros        enable row level security;  -- sem política: só service_role
alter table public.turnos            enable row level security;
alter table public.turno_tarefas     enable row level security;

-- ---------------------------------------------------------------------------
-- Auxiliares (security definer evita recursão de RLS entre tabelas)
-- ---------------------------------------------------------------------------

create function public.minha_familia_id() returns uuid
language sql stable security definer set search_path = ''
as $$ select id from public.familias where perfil_id = auth.uid() $$;

create function public.minha_residencia_id() returns uuid
language sql stable security definer set search_path = ''
as $$ select residencia_id from public.familias where perfil_id = auth.uid() $$;

create function public.minha_diarista_id() returns uuid
language sql stable security definer set search_path = ''
as $$ select id from public.diaristas where perfil_id = auth.uid() $$;

-- ---------------------------------------------------------------------------
-- Leitura
-- ---------------------------------------------------------------------------

grant select on public.perfis to authenticated;
grant update (nome, telefone) on public.perfis to authenticated;  -- nunca 'papel'
create policy perfis_leitura on public.perfis for select to authenticated
  using (id = auth.uid());
create policy perfis_edicao on public.perfis for update to authenticated
  using (id = auth.uid()) with check (id = auth.uid());

-- Família: não expõe CPF do pagador a ninguém além do service_role.
grant select (id, residencia_id, nome_responsavel, criado_em) on public.familias to authenticated;
create policy familias_leitura on public.familias for select to authenticated
  using (
    perfil_id = auth.uid()
    or id in (select familia_id from public.turnos where diarista_id = public.minha_diarista_id())
  );

grant select (id, logradouro, condominio, quadra, lote, cep) on public.residencias to authenticated;
create policy residencias_leitura on public.residencias for select to authenticated
  using (
    id = public.minha_residencia_id()
    or id in (select residencia_id from public.turnos where diarista_id = public.minha_diarista_id())
  );

grant select (id, perfil_id, regime, cnpj, cnae, valor_diaria_centavos, ativo, documentos_validados_em)
  on public.diaristas to authenticated;
create policy diaristas_leitura on public.diaristas for select to authenticated
  using (
    perfil_id = auth.uid()
    or id in (select diarista_id from public.turnos where residencia_id = public.minha_residencia_id())
  );

grant select on public.catalogo_tarefas to authenticated;
create policy catalogo_leitura on public.catalogo_tarefas for select to authenticated using (true);

grant select, insert, delete on public.diarista_tarefas to authenticated;
create policy diarista_tarefas_leitura on public.diarista_tarefas for select to authenticated using (true);
create policy diarista_tarefas_inclusao on public.diarista_tarefas for insert to authenticated
  with check (diarista_id = public.minha_diarista_id());
create policy diarista_tarefas_remocao on public.diarista_tarefas for delete to authenticated
  using (diarista_id = public.minha_diarista_id());

grant select on public.turnos to authenticated;
create policy turnos_leitura on public.turnos for select to authenticated
  using (
    residencia_id = public.minha_residencia_id()
    or diarista_id = public.minha_diarista_id()
  );

grant select on public.turno_tarefas to authenticated;
create policy turno_tarefas_leitura on public.turno_tarefas for select to authenticated
  using (exists (select 1 from public.turnos t where t.id = turno_id));

grant select on public.diarista_faturamento_ano to authenticated;

-- Vitrine: diaristas liberadas para receber pedidos (sem CPF/CNPJ).
create view public.diaristas_disponiveis as
select d.id, p.nome, d.valor_diaria_centavos
  from public.diaristas d
  join public.perfis p on p.id = d.perfil_id
 where d.ativo
   and d.documentos_validados_em is not null
   and d.valor_diaria_centavos is not null;
grant select on public.diaristas_disponiveis to authenticated;

-- ---------------------------------------------------------------------------
-- Escrita via funções
-- ---------------------------------------------------------------------------

create function public.registrar_familia(
  p_nome text, p_cpf text,
  p_condominio text, p_quadra text, p_lote text, p_cep text,
  p_logradouro text default null
) returns uuid
language plpgsql security definer set search_path = ''
as $$
declare
  v_uid uuid := auth.uid();
  v_res uuid;
  v_fam uuid;
begin
  if v_uid is null then
    raise exception 'nao_autenticado' using errcode = '28000';
  end if;

  insert into public.perfis (id, papel, nome) values (v_uid, 'familia', p_nome);

  insert into public.residencias (condominio, quadra, lote, cep, logradouro)
  values (p_condominio, p_quadra, p_lote, p_cep, p_logradouro)
  on conflict (chave) do nothing;

  select id into v_res from public.residencias
   where chave = lower(btrim(p_condominio)) || '|' || lower(btrim(p_quadra)) || '|' || lower(btrim(p_lote));

  insert into public.familias (perfil_id, residencia_id, nome_responsavel, cpf_pagador)
  values (v_uid, v_res, p_nome, p_cpf)
  returning id into v_fam;

  return v_fam;
end;
$$;

-- A diarista nasce sem 'documentos_validados_em': só entra na vitrine depois
-- da curadoria (service_role).
create function public.registrar_diarista(
  p_nome text, p_cpf text, p_cnpj text, p_valor_diaria_centavos integer
) returns uuid
language plpgsql security definer set search_path = ''
as $$
declare
  v_uid uuid := auth.uid();
  v_id uuid;
begin
  if v_uid is null then
    raise exception 'nao_autenticado' using errcode = '28000';
  end if;

  insert into public.perfis (id, papel, nome) values (v_uid, 'diarista', p_nome);
  insert into public.diaristas (perfil_id, cpf, cnpj, valor_diaria_centavos)
  values (v_uid, p_cpf, p_cnpj, p_valor_diaria_centavos)
  returning id into v_id;

  return v_id;
end;
$$;

create function public.solicitar_turno(
  p_diarista uuid, p_data date, p_inicio time, p_fim time,
  p_pausa integer default 60, p_deslocamento_modo text default null
) returns uuid
language plpgsql security definer set search_path = ''
as $$
declare
  v_fam public.familias;
  v_dia public.diaristas;
  v_id  uuid;
begin
  select * into v_fam from public.familias where perfil_id = auth.uid();
  if not found then
    raise exception 'apenas_familia' using errcode = '42501';
  end if;

  if p_data < (now() at time zone 'America/Sao_Paulo')::date then
    raise exception 'data_no_passado' using errcode = 'check_violation';
  end if;

  select * into v_dia from public.diaristas
   where id = p_diarista and ativo
     and documentos_validados_em is not null and valor_diaria_centavos is not null;
  if not found then
    raise exception 'diarista_indisponivel' using errcode = 'P0002';
  end if;

  insert into public.turnos (residencia_id, familia_id, diarista_id, data, hora_inicio, hora_fim,
                             pausa_minutos, valor_diaria_centavos, deslocamento_modo)
  values (v_fam.residencia_id, v_fam.id, v_dia.id, p_data, p_inicio, p_fim,
          p_pausa, v_dia.valor_diaria_centavos, p_deslocamento_modo)
  returning id into v_id;

  return v_id;
end;
$$;

-- A diarista aceita ou recusa sem penalidade (autonomia).
create function public.responder_turno(p_turno uuid, p_aceitar boolean) returns void
language plpgsql security definer set search_path = ''
as $$
begin
  update public.turnos
     set status = case when p_aceitar then 'confirmado' else 'recusado_diarista' end
   where id = p_turno
     and diarista_id = public.minha_diarista_id()
     and status = 'solicitado';
  if not found then
    raise exception 'turno_indisponivel' using errcode = 'P0002';
  end if;
end;
$$;

create function public.cancelar_turno_familia(p_turno uuid) returns void
language plpgsql security definer set search_path = ''
as $$
begin
  update public.turnos
     set status = 'cancelado_familia'
   where id = p_turno
     and residencia_id = public.minha_residencia_id()
     and status in ('solicitado', 'confirmado');
  if not found then
    raise exception 'turno_indisponivel' using errcode = 'P0002';
  end if;
end;
$$;

-- Fecha todas as funções do projeto e reabre só as que o cliente pode chamar.
do $$
declare f record;
begin
  for f in
    select p.oid::regprocedure as assinatura
      from pg_proc p
      join pg_namespace n on n.oid = p.pronamespace
     where n.nspname = 'public'
       and p.prokind = 'f'
       and not exists (select 1 from pg_depend d where d.objid = p.oid and d.deptype = 'e')
  loop
    execute format('revoke all on function %s from public, anon, authenticated', f.assinatura);
  end loop;
end $$;

grant execute on function
  public.minha_familia_id(), public.minha_residencia_id(), public.minha_diarista_id(),
  public.registrar_familia(text, text, text, text, text, text, text),
  public.registrar_diarista(text, text, text, integer),
  public.solicitar_turno(uuid, date, time, time, integer, text),
  public.responder_turno(uuid, boolean),
  public.cancelar_turno_familia(uuid)
to authenticated;
