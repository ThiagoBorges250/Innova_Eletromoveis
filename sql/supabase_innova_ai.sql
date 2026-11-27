-- Execute no SQL Editor do projeto Supabase associado ao catálogo.
begin;

create schema if not exists extensions;
create extension if not exists vector with schema extensions;

create table if not exists public.produtos_vetoriais (
    id bigserial primary key,
    produto_id text unique not null,
    conteudo text not null,
    embedding extensions.vector(384) not null
);

do $$
begin
    if not exists (
        select 1 from pg_catalog.pg_attribute
        where attrelid = 'public.produtos_vetoriais'::regclass
          and attname = 'embedding'
          and atttypid = 'extensions.vector'::regtype
          and atttypmod = 384
          and not attisdropped
    ) then
        raise exception 'public.produtos_vetoriais.embedding deve ser extensions.vector(384)';
    end if;
end;
$$;

alter table public.produtos_vetoriais add column if not exists modelo_embedding text;
alter table public.produtos_vetoriais enable row level security;
revoke all on table public.produtos_vetoriais from public, anon, authenticated;
grant select, insert, update, delete on table public.produtos_vetoriais to service_role;
grant usage on schema extensions to service_role;

do $$
declare
    sequencia text := pg_catalog.pg_get_serial_sequence('public.produtos_vetoriais', 'id');
    assinatura regprocedure;
begin
    if sequencia is not null then
        execute 'revoke all on sequence ' || sequencia || ' from public, anon, authenticated';
        execute 'grant usage on sequence ' || sequencia || ' to service_role';
    end if;

    -- Restringe assinaturas existentes da RPC a chamadas do backend.
    for assinatura in
        select p.oid::regprocedure from pg_catalog.pg_proc p
        join pg_catalog.pg_namespace n on n.oid = p.pronamespace
        where n.nspname = 'public' and p.proname = 'buscar_produtos' and p.prokind = 'f'
    loop
        execute 'revoke all on function ' || assinatura || ' from public, anon, authenticated';
    end loop;
end;
$$;

drop policy if exists innova_ai_backend on public.produtos_vetoriais;
create policy innova_ai_backend on public.produtos_vetoriais
    for all to service_role using (true) with check (true);

create index if not exists innova_produtos_embedding_hnsw
    on public.produtos_vetoriais using hnsw (embedding extensions.vector_cosine_ops)
    where modelo_embedding is not null;

create or replace function public.buscar_produtos(
    embedding_consulta extensions.vector(384),
    modelo_consulta text,
    limite integer default 40,
    ids_permitidos text[] default null
)
returns table (produto_id text, similaridade double precision)
language plpgsql stable security invoker
set search_path = pg_catalog, extensions
set hnsw.ef_search = 100
as $$
begin
    if ids_permitidos is null then
        return query
        select p.produto_id, 1 - (p.embedding <=> embedding_consulta)
        from public.produtos_vetoriais p
        where p.modelo_embedding is not null and p.modelo_embedding = modelo_consulta
          and p.embedding is not null
        order by p.embedding <=> embedding_consulta
        limit least(greatest(coalesce(limite, 40), 1), 100);
    else
        -- Busca exata no conjunto elegível filtrado pelo MongoDB.
        return query
        with elegiveis as materialized (
            select p.produto_id, p.embedding <=> embedding_consulta as distancia
            from public.produtos_vetoriais p
            where p.produto_id = any(ids_permitidos) and p.modelo_embedding = modelo_consulta
              and p.embedding is not null
        )
        select e.produto_id, 1 - e.distancia
        from elegiveis e
        order by e.distancia, e.produto_id
        limit least(greatest(coalesce(limite, 40), 1), 100);
    end if;
end;
$$;

revoke all on function public.buscar_produtos(extensions.vector, text, integer, text[])
    from public, anon, authenticated;
grant execute on function public.buscar_produtos(extensions.vector, text, integer, text[])
    to service_role;
notify pgrst, 'reload schema';

commit;
