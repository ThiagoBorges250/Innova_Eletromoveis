

create table if not exists public.admins (
    user_id uuid primary key references auth.users (id) on delete cascade,
    criado_em timestamptz not null default now()
);

alter table public.admins enable row level security;

revoke all on public.admins from anon, authenticated;

insert into public.admins (user_id)
select id from auth.users where email = 'admin@exemplo.com'
on conflict (user_id) do nothing;


