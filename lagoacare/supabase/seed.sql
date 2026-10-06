-- Catálogo inicial. Tudo 'pendente' até o contador confirmar o enquadramento
-- de cada tarefa na ocupação MEI (CNAE 9700-5/00).
insert into public.catalogo_tarefas (codigo, nome, categoria) values
  ('limpeza_geral',    'Limpeza geral',                 'limpeza'),
  ('organizacao_casa', 'Organização da casa',           'limpeza'),
  ('cozinha',          'Preparo de refeições e cozinha','cozinha'),
  ('lavanderia',       'Lavanderia e passadoria',       'roupas'),
  ('cuidado_infantil', 'Cuidado infantil',              'cuidado_infantil')
on conflict (codigo) do nothing;
