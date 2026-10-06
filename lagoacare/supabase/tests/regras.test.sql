-- Testes das regras de agenda e de acesso. Rodam em uma transação revertida.
-- Datas: 2027-03-01 é segunda-feira.
begin;

create function pg_temp.falha(q text, esperado text) returns void language plpgsql as $$
declare falhou boolean := false;
begin
  begin
    execute q;
  exception when others then
    if sqlstate <> esperado then
      raise exception 'erro % (%), esperado %: %', sqlstate, sqlerrm, esperado, q;
    end if;
    falhou := true;
  end;
  if not falhou then raise exception 'esperava falha % em: %', esperado, q; end if;
end $$;

create function pg_temp.turno(p_dia uuid, p_res uuid, p_fam uuid, p_data date,
                              p_status text default 'confirmado',
                              p_ini time default '08:00', p_fim time default '17:00')
returns uuid language sql as $$
  insert into public.turnos (diarista_id, residencia_id, familia_id, data, hora_inicio, hora_fim,
                             status, valor_diaria_centavos)
  values (p_dia, p_res, p_fam, p_data, p_ini, p_fim, p_status, 20000)
  returning id
$$;

-- Fixtures -------------------------------------------------------------------
insert into auth.users (id) values
  ('00000000-0000-0000-0000-0000000000a1'), ('00000000-0000-0000-0000-0000000000a2'),
  ('00000000-0000-0000-0000-0000000000d1'), ('00000000-0000-0000-0000-0000000000d2'),
  ('00000000-0000-0000-0000-0000000000d3');

insert into public.perfis (id, papel, nome) values
  ('00000000-0000-0000-0000-0000000000a1', 'familia', 'Familia 1'),
  ('00000000-0000-0000-0000-0000000000a2', 'familia', 'Familia 2'),
  ('00000000-0000-0000-0000-0000000000d1', 'diarista', 'Diarista 1'),
  ('00000000-0000-0000-0000-0000000000d2', 'diarista', 'Diarista 2'),
  ('00000000-0000-0000-0000-0000000000d3', 'diarista', 'Diarista 3');

insert into public.residencias (id, condominio, quadra, lote, cep) values
  ('00000000-0000-0000-0000-00000000aa01', 'Alphaville', 'A', '1', '34000000'),
  ('00000000-0000-0000-0000-00000000aa02', 'Alphaville', 'B', '2', '34000000');

insert into public.familias (id, perfil_id, residencia_id, nome_responsavel, cpf_pagador) values
  ('00000000-0000-0000-0000-00000000f001', '00000000-0000-0000-0000-0000000000a1',
   '00000000-0000-0000-0000-00000000aa01', 'Familia 1', '11111111111'),
  ('00000000-0000-0000-0000-00000000f002', '00000000-0000-0000-0000-0000000000a2',
   '00000000-0000-0000-0000-00000000aa02', 'Familia 2', '22222222222');

insert into public.diaristas (id, perfil_id, cpf, cnpj, valor_diaria_centavos, documentos_validados_em) values
  ('00000000-0000-0000-0000-00000000d001', '00000000-0000-0000-0000-0000000000d1', '33333333331', '10000000000001', 20000, now()),
  ('00000000-0000-0000-0000-00000000d002', '00000000-0000-0000-0000-0000000000d2', '33333333332', '10000000000002', 20000, now()),
  ('00000000-0000-0000-0000-00000000d003', '00000000-0000-0000-0000-0000000000d3', '33333333333', '10000000000003', 20000, null);


-- Constantes reutilizadas pelos blocos abaixo
create temp table c as select
  '00000000-0000-0000-0000-00000000d001'::uuid d1, '00000000-0000-0000-0000-00000000d002'::uuid d2,
  '00000000-0000-0000-0000-00000000d003'::uuid d3,
  '00000000-0000-0000-0000-00000000aa01'::uuid r1, '00000000-0000-0000-0000-00000000aa02'::uuid r2,
  '00000000-0000-0000-0000-00000000f001'::uuid f1, '00000000-0000-0000-0000-00000000f002'::uuid f2;
grant select on c to authenticated;

-- Regra 1: janela móvel de 7 dias ---------------------------------------------
do $$
declare k c;
begin
  select * into k from c;
  -- seg + qui + seg seguinte: válido (nenhuma janela de 7 dias contém 3 dias)
  perform pg_temp.turno(k.d1, k.r1, k.f1, date '2027-03-01');
  perform pg_temp.turno(k.d1, k.r1, k.f1, date '2027-03-04');
  perform pg_temp.turno(k.d1, k.r1, k.f1, date '2027-03-08');
  -- domingo 03-07 formaria seg+qui+dom na janela 03-01..03-07
  perform pg_temp.falha(format('select pg_temp.turno(%L,%L,%L,date ''2027-03-07'')', k.d1, k.r1, k.f1), '23514');
  -- 03-02 (ter) formaria seg+ter+qui na janela 03-01..03-07
  perform pg_temp.falha(format('select pg_temp.turno(%L,%L,%L,date ''2027-03-02'')', k.d1, k.r1, k.f1), '23514');
  -- outro dia distante é livre
  perform pg_temp.turno(k.d1, k.r1, k.f1, date '2027-03-22');
  raise notice 'ok: janela móvel de 7 dias';
end $$;

-- Escopo do contador: outra residência e outra diarista não são afetadas -------
do $$
declare k c;
begin
  select * into k from c;
  -- mesma diarista, outra residência (R2): 2 dias livres, em datas sem sobrepor com R1
  perform pg_temp.turno(k.d1, k.r2, k.f2, date '2027-03-02');
  perform pg_temp.turno(k.d1, k.r2, k.f2, date '2027-03-05');
  -- outra diarista na mesma residência R1 nos mesmos dias que a D1 estourou
  perform pg_temp.turno(k.d2, k.r1, k.f1, date '2027-03-02');
  perform pg_temp.turno(k.d2, k.r1, k.f1, date '2027-03-03');
  raise notice 'ok: escopo por par diarista x residência';
end $$;

-- Cancelamento ------------------------------------------------------------------
do $$
declare k c; t uuid; hoje date := (now() at time zone 'America/Sao_Paulo')::date;
begin
  select * into k from c;
  -- Cancelado com antecedência: libera o dia no contador
  perform pg_temp.turno(k.d2, k.r2, k.f2, date '2027-06-01');
  t := pg_temp.turno(k.d2, k.r2, k.f2, date '2027-06-03');
  update public.turnos set status = 'cancelado_familia' where id = t;
  perform pg_temp.turno(k.d2, k.r2, k.f2, date '2027-06-04');  -- 3º dia, mas o 03 foi liberado
  if (select cancelamento_tardio from public.turnos where id = t) then
    raise exception 'cancelamento antecipado marcado como tardio';
  end if;

  -- Cancelamento tardio (< 24h) continua contando
  perform pg_temp.turno(k.d1, k.r2, k.f2, hoje, 'cancelado_familia');   -- tardio: conta
  perform pg_temp.turno(k.d1, k.r2, k.f2, hoje + 3);
  perform pg_temp.falha(format('select pg_temp.turno(%L,%L,%L,%L::date)', k.d1, k.r2, k.f2, hoje + 5), '23514');
  -- cancelado com muita antecedência não conta: hoje+30 (cancelado) + hoje+31 + hoje+32
  perform pg_temp.turno(k.d1, k.r2, k.f2, hoje + 30, 'cancelado_familia');
  perform pg_temp.turno(k.d1, k.r2, k.f2, hoje + 31);
  perform pg_temp.turno(k.d1, k.r2, k.f2, hoje + 32);
  raise notice 'ok: cancelamento antecipado x tardio';
end $$;

-- Recusa da diarista não conta e não ocupa a agenda -------------------------------
do $$
declare k c;
begin
  select * into k from c;
  perform pg_temp.turno(k.d2, k.r1, k.f1, date '2027-09-01', 'recusado_diarista');
  perform pg_temp.turno(k.d2, k.r1, k.f1, date '2027-09-02', 'recusado_diarista');
  perform pg_temp.turno(k.d2, k.r1, k.f1, date '2027-09-03', 'recusado_diarista');
  perform pg_temp.turno(k.d2, k.r1, k.f1, date '2027-09-04');
  raise notice 'ok: recusa não conta';
end $$;

-- Jornada e agenda -----------------------------------------------------------------
do $$
declare k c;
begin
  select * into k from c;
  -- 08:00-17:00 com 1h de pausa = 8h de trabalho: válido
  perform pg_temp.turno(k.d1, k.r1, k.f1, date '2028-01-10', 'confirmado', '08:00', '17:00');
  -- 08:00-18:00 = 9h de trabalho: recusado
  perform pg_temp.falha(format('select pg_temp.turno(%L,%L,%L,date ''2028-01-20'',''confirmado'',''08:00'',''18:00'')',
                               k.d1, k.r1, k.f1), '23514');
  -- pausa menor que 1h: recusada
  perform pg_temp.falha(format($q$insert into public.turnos (diarista_id,residencia_id,familia_id,data,hora_inicio,hora_fim,pausa_minutos,valor_diaria_centavos)
                                  values (%L,%L,%L,date '2028-01-21','08:00','16:00',30,20000)$q$, k.d1, k.r1, k.f1), '23514');
  -- sobreposição da mesma diarista em outra residência no mesmo dia
  perform pg_temp.falha(format('select pg_temp.turno(%L,%L,%L,date ''2028-01-10'',''confirmado'',''12:00'',''16:00'')',
                               k.d1, k.r2, k.f2), '23P01');
  -- família x residência incoerentes
  perform pg_temp.falha(format('select pg_temp.turno(%L,%L,%L,date ''2028-02-01'')', k.d1, k.r2, k.f1), '23503');
  raise notice 'ok: jornada, pausa, sobreposição e coerência família/residência';
end $$;

-- Faturamento: só diárias concluídas, alerta a partir de 80% do teto -----------------
do $$
declare k c; a boolean; p numeric;
begin
  select * into k from c;
  update public.parametros set valor = 100000 where chave = 'teto_mei_anual_centavos';
  perform pg_temp.turno(k.d1, k.r1, k.f1, date '2029-05-03', 'concluido');
  perform pg_temp.turno(k.d1, k.r1, k.f1, date '2029-05-10', 'concluido');
  perform pg_temp.turno(k.d1, k.r1, k.f1, date '2029-05-17', 'confirmado');
  select alerta_teto, percentual_teto into a, p
    from public.diarista_faturamento_ano where diarista_id = k.d1 and ano = 2029;
  if p <> 40.0 or a then raise exception 'faturamento inesperado: % %', p, a; end if;
  perform pg_temp.turno(k.d1, k.r1, k.f1, date '2029-06-07', 'concluido');
  perform pg_temp.turno(k.d1, k.r1, k.f1, date '2029-06-14', 'concluido');
  select alerta_teto into a from public.diarista_faturamento_ano where diarista_id = k.d1 and ano = 2029;
  if not a then raise exception 'alerta de teto deveria disparar'; end if;
  raise notice 'ok: faturamento e alerta de teto';
end $$;

-- Acesso (RLS) -------------------------------------------------------------------------
do $$
declare n integer;
begin
  -- Família 2 (R2) só enxerga turnos da própria residência
  perform set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-0000000000a2', true);
  set local role authenticated;
  select count(*) into n from public.turnos where residencia_id <> (select r2 from c);
  if n <> 0 then raise exception 'família enxerga turnos de outra residência (%)', n; end if;
  select count(*) into n from public.turnos;
  if n = 0 then raise exception 'família deveria enxergar os próprios turnos'; end if;

  -- Tabelas fechadas e colunas protegidas
  perform pg_temp.falha('select * from public.parametros', '42501');
  perform pg_temp.falha('select cpf_pagador from public.familias', '42501');
  perform pg_temp.falha($q$update public.perfis set papel = 'admin'$q$, '42501');
  perform pg_temp.falha('select cpf from public.diaristas', '42501');
  perform pg_temp.falha($q$insert into public.turnos (residencia_id) values (gen_random_uuid())$q$, '42501');

  -- Vitrine só traz diarista validada (D3 não foi validada)
  select count(*) into n from public.diaristas_disponiveis;
  if n <> 2 then raise exception 'vitrine deveria listar 2 diaristas, listou %', n; end if;

  -- anon não executa funções nem lê nada
  reset role;
  set local role anon;
  perform pg_temp.falha('select public.minha_familia_id()', '42501');
  perform pg_temp.falha('select * from public.turnos', '42501');
  reset role;
  raise notice 'ok: RLS e permissões';
end $$;

-- Funções de aplicação: fluxo completo --------------------------------------------------
do $$
declare
  novo_f uuid := '00000000-0000-0000-0000-0000000000b1';
  novo_d uuid := '00000000-0000-0000-0000-0000000000b2';
  outra_f uuid := '00000000-0000-0000-0000-0000000000a2';
  r_antiga uuid; r_nova uuid; v_fam uuid; v_dia uuid; v_turno uuid; v_st text; v_tardio boolean;
begin
  insert into auth.users (id) values (novo_f), (novo_d);

  -- Mesmo endereço digitado de formas diferentes cai na mesma residência
  perform set_config('request.jwt.claim.sub', novo_f::text, true);
  set local role authenticated;
  v_fam := public.registrar_familia('Nova Familia', '44444444444', ' alphaville ', 'a', '1 ', '34000000');
  reset role;
  select residencia_id into r_nova from public.familias where id = v_fam;
  select id into r_antiga from public.residencias where chave = 'alphaville|a|1';
  if r_nova <> r_antiga then raise exception 'residência duplicada: a chave normalizada falhou'; end if;

  -- Diarista se cadastra, mas ainda não pode receber pedidos (sem curadoria)
  perform set_config('request.jwt.claim.sub', novo_d::text, true);
  set local role authenticated;
  v_dia := public.registrar_diarista('Nova Diarista', '55555555555', '20000000000001', 25000);
  perform pg_temp.falha($q$select public.solicitar_turno(null, date '2030-03-04', '08:00', '17:00')$q$, '42501');  -- diarista não solicita
  reset role;

  perform set_config('request.jwt.claim.sub', novo_f::text, true);
  set local role authenticated;
  perform pg_temp.falha(format($q$select public.solicitar_turno(%L, date '2030-03-04', '08:00', '17:00')$q$, v_dia), 'P0002');
  reset role;

  update public.diaristas set documentos_validados_em = now() where id = v_dia;  -- curadoria

  -- Família pede 2030-03-04 (seg) e 03-06 (qua); o 3º dia na janela é barrado
  set local role authenticated;
  v_turno := public.solicitar_turno(v_dia, date '2030-03-04', '08:00', '17:00');
  perform public.solicitar_turno(v_dia, date '2030-03-06', '08:00', '17:00');
  perform pg_temp.falha(format($q$select public.solicitar_turno(%L, date '2030-03-08', '08:00', '17:00')$q$, v_dia), '23514');
  perform pg_temp.falha(format($q$select public.solicitar_turno(%L, date '2001-01-01', '08:00', '17:00')$q$, v_dia), '23514');
  reset role;

  -- O preço vem do perfil da diarista, não do pedido da família
  if (select valor_diaria_centavos from public.turnos where id = v_turno) <> 25000 then
    raise exception 'valor da diária deveria vir do perfil da diarista';
  end if;

  -- Outra família não cancela turno alheio
  perform set_config('request.jwt.claim.sub', outra_f::text, true);
  set local role authenticated;
  perform pg_temp.falha(format($q$select public.cancelar_turno_familia(%L)$q$, v_turno), 'P0002');
  reset role;

  -- A diarista confirma
  perform set_config('request.jwt.claim.sub', novo_d::text, true);
  set local role authenticated;
  perform public.responder_turno(v_turno, true);
  reset role;
  select status into v_st from public.turnos where id = v_turno;
  if v_st <> 'confirmado' then raise exception 'esperava confirmado, veio %', v_st; end if;

  -- A família cancela com antecedência: libera o dia e o 3º pedido passa a valer
  perform set_config('request.jwt.claim.sub', novo_f::text, true);
  set local role authenticated;
  perform public.cancelar_turno_familia(v_turno);
  perform public.solicitar_turno(v_dia, date '2030-03-08', '08:00', '17:00');
  reset role;
  select status, cancelamento_tardio into v_st, v_tardio from public.turnos where id = v_turno;
  if v_st <> 'cancelado_familia' or v_tardio then raise exception 'cancelamento incorreto: % %', v_st, v_tardio; end if;

  raise notice 'ok: fluxo registrar -> solicitar -> responder -> cancelar';
end $$;

rollback;
