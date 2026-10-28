-- Sparqle washer accounts and training: database setup for Supabase.
-- Run once in the Supabase dashboard: SQL Editor > New query > paste this file > Run.
-- Safe to run again; it updates functions and policies in place.
--
-- This file holds no training content or quiz answers. Those are loaded
-- separately from training-content.sql, which is kept out of this public repo.

-- ---------- tables ----------

-- One row per washer account, created automatically at sign-up.
create table if not exists public.washers (
  id          uuid primary key references auth.users (id) on delete cascade,
  full_name   text not null default '',
  phone       text not null default '',
  email       text not null default '',
  status      text not null default 'pending' check (status in ('pending', 'approved', 'revoked')),
  created_at  timestamptz not null default now(),
  approved_at timestamptz
);

-- Emails that can see the admin view (washer approvals and quiz results).
create table if not exists public.admins (
  email text primary key
);
insert into public.admins (email) values ('admin@elitedigitalconsulting.com.au')
  on conflict do nothing;

-- The course: modules and quiz questions, without the answers.
create table if not exists public.training_content (
  id         int primary key default 1 check (id = 1),
  modules    jsonb not null,
  questions  jsonb not null,
  pass_mark  int not null,
  updated_at timestamptz not null default now()
);

-- The quiz answers. No one can read this through the website; only submit_quiz() uses it.
create table if not exists public.quiz_key (
  id      int primary key default 1 check (id = 1),
  answers jsonb not null
);

-- Every quiz attempt.
create table if not exists public.quiz_results (
  id          bigint generated always as identity primary key,
  user_id     uuid not null references public.washers (id) on delete cascade,
  name        text not null default '',
  score       int not null,
  total       int not null,
  passed      boolean not null,
  critical_ok boolean not null,
  answers     jsonb not null,
  created_at  timestamptz not null default now()
);
create index if not exists quiz_results_user_idx on public.quiz_results (user_id, created_at desc);

-- ---------- helper checks ----------

-- True when the signed-in person's confirmed email is on the admins list.
create or replace function public.is_admin()
returns boolean
language sql stable security definer set search_path = public
as $$
  select exists (
    select 1
    from auth.users u
    join public.admins a on lower(a.email) = lower(u.email)
    where u.id = auth.uid() and u.email_confirmed_at is not null
  );
$$;

-- True when the signed-in washer has been approved.
create or replace function public.is_approved()
returns boolean
language sql stable security definer set search_path = public
as $$
  select exists (select 1 from public.washers where id = auth.uid() and status = 'approved');
$$;

-- ---------- sign-up ----------

-- Copies name, mobile and email from the sign-up form into public.washers.
create or replace function public.handle_new_washer()
returns trigger
language plpgsql security definer set search_path = public
as $$
begin
  insert into public.washers (id, full_name, phone, email)
  values (
    new.id,
    left(coalesce(new.raw_user_meta_data ->> 'full_name', ''), 120),
    left(coalesce(new.raw_user_meta_data ->> 'phone', ''), 40),
    coalesce(new.email, '')
  )
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_washer();

-- ---------- admin actions ----------

create or replace function public.set_washer_status(p_id uuid, p_status text)
returns void
language plpgsql security definer set search_path = public
as $$
begin
  if not public.is_admin() then
    raise exception 'Only admins can change washer access' using errcode = '42501';
  end if;
  if p_status not in ('pending', 'approved', 'revoked') then
    raise exception 'Unknown status %', p_status using errcode = '22023';
  end if;
  update public.washers
     set status = p_status,
         approved_at = case when p_status = 'approved' then coalesce(approved_at, now()) else approved_at end
   where id = p_id;
end;
$$;

-- ---------- quiz ----------

-- Marks a washer's answers against quiz_key, saves the attempt and returns the result.
-- p_answers is an array with one chosen option index per question, in question order.
create or replace function public.submit_quiz(p_answers jsonb)
returns jsonb
language plpgsql security definer set search_path = public
as $$
declare
  w        public.washers%rowtype;
  k        public.quiz_key%rowtype;
  qs       jsonb;
  pass     int;
  n        int;
  i        int;
  chosen   int;
  correct  int;
  is_crit  boolean;
  ok       boolean;
  score    int := 0;
  crit_ok  boolean := true;
  passed   boolean;
  marks    jsonb := '[]'::jsonb;
  recent   int;
begin
  select * into w from public.washers where id = auth.uid();
  if not found or (w.status <> 'approved' and not public.is_admin()) then
    raise exception 'Your account has not been approved yet' using errcode = '42501';
  end if;

  select count(*) into recent from public.quiz_results
   where user_id = auth.uid() and created_at > now() - interval '24 hours';
  if recent >= 5 then
    raise exception 'too_many_attempts' using errcode = 'P0001';
  end if;

  select * into k from public.quiz_key where id = 1;
  select questions, pass_mark into qs, pass from public.training_content where id = 1;
  if k.id is null or qs is null then
    raise exception 'The quiz has not been set up yet' using errcode = 'P0001';
  end if;

  n := jsonb_array_length(k.answers);
  if jsonb_typeof(p_answers) is distinct from 'array' or jsonb_array_length(p_answers) <> n then
    raise exception 'Answer every question before submitting' using errcode = '22023';
  end if;

  for i in 0 .. n - 1 loop
    chosen  := case when jsonb_typeof(p_answers -> i) = 'number' then (p_answers ->> i)::int end;
    correct := (k.answers -> i ->> 'correct')::int;
    is_crit := coalesce((qs -> i ->> 'critical')::boolean, false);
    ok      := chosen is not distinct from correct;
    if ok then
      score := score + 1;
    elsif is_crit then
      crit_ok := false;
    end if;
    marks := marks || jsonb_build_array(jsonb_build_object(
      'ok', ok, 'chosen', chosen, 'correct', correct, 'why', k.answers -> i ->> 'why'));
  end loop;

  passed := score >= pass and crit_ok;

  insert into public.quiz_results (user_id, name, score, total, passed, critical_ok, answers)
  values (auth.uid(), w.full_name, score, n, passed, crit_ok, p_answers);

  return jsonb_build_object(
    'score', score, 'total', n, 'passed', passed, 'critical_ok', crit_ok,
    'pass_mark', pass, 'marks', marks, 'at', now());
end;
$$;

-- ---------- access rules ----------

alter table public.washers          enable row level security;
alter table public.admins           enable row level security;
alter table public.training_content enable row level security;
alter table public.quiz_key         enable row level security;
alter table public.quiz_results     enable row level security;

drop policy if exists "washers: own row or admin" on public.washers;
create policy "washers: own row or admin" on public.washers
  for select to authenticated using (id = auth.uid() or public.is_admin());

drop policy if exists "training: approved washers and admins" on public.training_content;
create policy "training: approved washers and admins" on public.training_content
  for select to authenticated using (public.is_approved() or public.is_admin());

drop policy if exists "results: own or admin" on public.quiz_results;
create policy "results: own or admin" on public.quiz_results
  for select to authenticated using (user_id = auth.uid() or public.is_admin());

-- admins and quiz_key have no policies, so the website can't read them at all.
-- All writes go through the functions above, so no table has an insert, update or delete policy.

revoke all on public.washers, public.admins, public.training_content, public.quiz_key, public.quiz_results from anon, authenticated;
grant select on public.washers, public.training_content, public.quiz_results to authenticated;

revoke all on function public.is_admin(), public.is_approved(), public.set_washer_status(uuid, text), public.submit_quiz(jsonb) from public, anon;
grant execute on function public.is_admin(), public.is_approved(), public.set_washer_status(uuid, text), public.submit_quiz(jsonb) to authenticated;
revoke all on function public.handle_new_washer() from public, anon, authenticated;
