-- Run in Supabase → SQL Editor (once per project).
-- Enables per-user saved Project Gutenberg IDs.

create table if not exists public.saved_books (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  book_id integer not null,
  title text,
  created_at timestamptz not null default now(),
  unique (user_id, book_id)
);

alter table public.saved_books enable row level security;

drop policy if exists "saved_select_own" on public.saved_books;
drop policy if exists "saved_insert_own" on public.saved_books;
drop policy if exists "saved_update_own" on public.saved_books;
drop policy if exists "saved_delete_own" on public.saved_books;

create policy "saved_select_own" on public.saved_books
  for select using (auth.uid() = user_id);

create policy "saved_insert_own" on public.saved_books
  for insert with check (auth.uid() = user_id);

create policy "saved_update_own" on public.saved_books
  for update using (auth.uid() = user_id);

create policy "saved_delete_own" on public.saved_books
  for delete using (auth.uid() = user_id);

grant select, insert, update, delete on table public.saved_books to authenticated;
