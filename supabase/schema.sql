-- Panpacific University Scholarship System
-- Supabase schema (Postgres). Run this once in the Supabase SQL editor,
-- or against any Postgres database (the FastAPI backend uses the same shape).
--
-- Ownership split
--   Supabase  : Postgres database + Storage bucket for uploaded documents
--   FastAPI   : sign-in, roles, business rules
--   Browser   : talks to FastAPI only, never to Supabase directly
--
-- Soft delete convention
--   "active" queries       -> WHERE deleted_at IS NULL
--   history / audit query  -> no deleted_at filter (public.application_history
--                             has no deleted_at column at all, so the trail of
--                             what happened is never hidden)

-- gen_random_uuid() is part of PostgreSQL 13+ (Supabase runs 15+), so no
-- extension is required.

-- ---------------------------------------------------------------------------
-- users
-- ---------------------------------------------------------------------------
create table if not exists public.users (
  id            uuid primary key default gen_random_uuid(),
  auth_user_id  uuid unique,
  email         text not null,
  full_name     text not null,
  role          text not null default 'student'
                check (role in ('student', 'staff', 'admin')),
  password_hash text,
  student_id    text not null default '',
  program       text not null default '',
  year_level    text not null default '',
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  deleted_at    timestamptz
);

-- email is unique among accounts that are still active
create unique index if not exists users_email_unique
  on public.users (lower(email)) where deleted_at is null;

create index if not exists users_role_idx
  on public.users (role) where deleted_at is null;

-- auth_user_id links a row to Supabase Auth (auth.users.id) when
-- AUTH_PROVIDER=supabase. password_hash is filled only when AUTH_PROVIDER=local.

-- ---------------------------------------------------------------------------
-- terms (the term the system is currently on)
-- ---------------------------------------------------------------------------
create table if not exists public.terms (
  id            uuid primary key default gen_random_uuid(),
  trimester     text not null
                check (trimester in ('1st Trimester', '2nd Trimester', '3rd Trimester')),
  academic_year text not null,
  label         text not null,
  is_current    boolean not null default false,
  created_at    timestamptz not null default now(),
  created_by    uuid references public.users (id),
  deleted_at    timestamptz
);

-- only one active current term
create unique index if not exists terms_single_current
  on public.terms (is_current) where is_current and deleted_at is null;

-- ---------------------------------------------------------------------------
-- application code counter, one row per year (APP-<year>-<0000>)
-- ---------------------------------------------------------------------------
create table if not exists public.application_counters (
  year       integer primary key,
  last_value integer not null default 0
);

-- ---------------------------------------------------------------------------
-- applications
-- ---------------------------------------------------------------------------
create table if not exists public.applications (
  id               uuid primary key default gen_random_uuid(),
  code             text not null unique,
  student_user_id  uuid not null references public.users (id),
  term_id          uuid references public.terms (id),
  term_label       text not null,
  student_name     text not null,
  student_id       text not null,
  university_email text not null,
  program          text not null,
  year_level       text not null,
  gwa              text not null default '',
  scholarship_type text not null,
  status           text not null default 'Submitted'
                   check (status in ('Submitted', 'Under Evaluation', 'Approved', 'Rejected')),
  remarks          text not null default '',
  evaluated_by     text not null default '',
  discount_percent text not null default '',
  date_submitted   timestamptz not null default now(),
  archived         boolean not null default false,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now(),
  deleted_at       timestamptz
);

create index if not exists applications_active_idx
  on public.applications (date_submitted desc)
  where deleted_at is null and archived = false;

create index if not exists applications_student_idx
  on public.applications (student_user_id, date_submitted desc)
  where deleted_at is null;

create index if not exists applications_audit_idx
  on public.applications (deleted_at, archived);

-- ---------------------------------------------------------------------------
-- uploaded documents (metadata for files kept in Supabase Storage)
-- ---------------------------------------------------------------------------
create table if not exists public.application_documents (
  id              uuid primary key default gen_random_uuid(),
  application_id  uuid not null references public.applications (id) on delete cascade,
  requirement_key text not null,
  file_name       text not null,
  storage_path    text not null,
  content_type    text,
  size_bytes      bigint,
  uploaded_at     timestamptz not null default now(),
  deleted_at      timestamptz
);

create unique index if not exists application_documents_unique
  on public.application_documents (application_id, requirement_key)
  where deleted_at is null;

-- ---------------------------------------------------------------------------
-- status history (audit trail, append only, never soft deleted)
-- ---------------------------------------------------------------------------
create table if not exists public.application_history (
  id             uuid primary key default gen_random_uuid(),
  application_id uuid not null references public.applications (id) on delete cascade,
  status         text not null,
  remarks        text not null default '',
  actor_user_id  uuid references public.users (id),
  actor_name     text not null default '',
  created_at     timestamptz not null default now()
);

-- the audit query reads this table with NO deleted_at filter
create index if not exists application_history_app_idx
  on public.application_history (application_id, created_at);

create index if not exists application_history_created_idx
  on public.application_history (created_at desc);

-- ---------------------------------------------------------------------------
-- notifications
-- ---------------------------------------------------------------------------
create table if not exists public.notifications (
  id             uuid primary key default gen_random_uuid(),
  user_id        uuid not null references public.users (id) on delete cascade,
  application_id uuid references public.applications (id) on delete cascade,
  type           text not null default 'status' check (type in ('status', 'admin')),
  message        text not null,
  read           boolean not null default false,
  created_at     timestamptz not null default now(),
  deleted_at     timestamptz
);

create index if not exists notifications_user_idx
  on public.notifications (user_id, created_at desc) where deleted_at is null;

-- ---------------------------------------------------------------------------
-- password reset tokens (only used when AUTH_PROVIDER=local)
-- ---------------------------------------------------------------------------
create table if not exists public.password_reset_tokens (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references public.users (id) on delete cascade,
  token_hash text not null,
  expires_at timestamptz not null,
  used_at    timestamptz,
  created_at timestamptz not null default now()
);

create index if not exists password_reset_tokens_user_idx
  on public.password_reset_tokens (user_id, created_at desc);

-- ---------------------------------------------------------------------------
-- updated_at maintenance
-- ---------------------------------------------------------------------------
create or replace function public.touch_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists users_touch on public.users;
create trigger users_touch
  before update on public.users
  for each row execute function public.touch_updated_at();

drop trigger if exists applications_touch on public.applications;
create trigger applications_touch
  before update on public.applications
  for each row execute function public.touch_updated_at();

-- ---------------------------------------------------------------------------
-- Row Level Security
--
-- The backend connects as the database owner, so it is not affected by these
-- policies. They exist to make sure that nothing reachable with the anon /
-- publishable key can read or write application data.
-- ---------------------------------------------------------------------------
alter table public.users                 enable row level security;
alter table public.terms                 enable row level security;
alter table public.applications          enable row level security;
alter table public.application_documents enable row level security;
alter table public.application_history   enable row level security;
alter table public.notifications         enable row level security;
alter table public.application_counters  enable row level security;
alter table public.password_reset_tokens enable row level security;

do $$
begin
  if exists (select 1 from pg_roles where rolname = 'anon') then
    execute 'revoke all on all tables in schema public from anon, authenticated';
    execute 'revoke all on all sequences in schema public from anon, authenticated';
  end if;
end;
$$;

-- ---------------------------------------------------------------------------
-- Storage bucket for uploaded documents (private; the backend serves the files)
-- ---------------------------------------------------------------------------
do $$
begin
  if exists (
    select 1 from information_schema.tables
    where table_schema = 'storage' and table_name = 'buckets'
  ) then
    insert into storage.buckets (id, name, public)
    values ('scholarship-documents', 'scholarship-documents', false)
    on conflict (id) do nothing;
  end if;
end;
$$;

-- ---------------------------------------------------------------------------
-- First admin
--
-- 1. Register normally through template/register.html (creates a student row).
-- 2. Promote that row:
--      update public.users set role = 'admin' where lower(email) = lower('you@panpacificu.edu.ph');
--    (or run: python backend/scripts/promote_admin.py you@panpacificu.edu.ph)
-- ---------------------------------------------------------------------------
