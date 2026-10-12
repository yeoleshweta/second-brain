-- The Void cloud store. Run in the Supabase SQL editor.
-- Turn sign-ups off in Authentication → Providers after creating one user.

create table if not exists public.messages (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  session_id text not null,
  role text not null check (role in ('user', 'assistant')),
  content text not null,
  created_at timestamptz not null default now()
);

create table if not exists public.capture_outcomes (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  message_id uuid references public.messages (id) on delete set null,
  outcome text not null check (outcome in ('log', 'unsorted', 'none', 'queued')),
  path text,
  detail text,
  created_at timestamptz not null default now()
);

create table if not exists public.retry_queue (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  line text not null,
  attempts int not null default 0,
  created_at timestamptz not null default now()
);

alter table public.messages enable row level security;
alter table public.capture_outcomes enable row level security;
alter table public.retry_queue enable row level security;

create policy "own messages" on public.messages
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "own outcomes" on public.capture_outcomes
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "own retries" on public.retry_queue
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

insert into storage.buckets (id, name, public)
values ('captures', 'captures', false)
on conflict (id) do nothing;
