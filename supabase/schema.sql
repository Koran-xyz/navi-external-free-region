-- Navi External Free Region v0.1
-- Private Supabase project only. Do not insert personal data, company confidential data,
-- addresses, raw GPS data, credentials, or API keys in this shared research database.

create extension if not exists pgcrypto;

create table if not exists public.projects (
  id uuid primary key default gen_random_uuid(),
  project_code text not null unique,
  title text not null,
  purpose text not null,
  current_state text not null,
  next_action text not null,
  status text not null check (status in ('active', 'blocked', 'approval_required', 'completed')),
  meta_rule_version text not null,
  updated_at timestamptz not null default now()
);

create table if not exists public.agents (
  id uuid primary key default gen_random_uuid(),
  agent_code text not null unique,
  display_name text not null,
  role text not null,
  platform text not null,
  status text not null check (status in ('available', 'waiting', 'disabled')),
  updated_at timestamptz not null default now()
);

create table if not exists public.work_logs (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete restrict,
  actor_code text not null,
  kind text not null,
  content text not null,
  evidence text not null default '',
  result text not null default '',
  next_action text not null default '',
  status text not null check (status in ('reported', 'in_progress', 'blocked', 'approval_required', 'completed')),
  approval_required boolean not null default false,
  created_at timestamptz not null default now()
);

create table if not exists public.handoffs (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete restrict,
  from_actor text not null,
  to_actor text not null,
  purpose text not null,
  current_state text not null,
  task text not null,
  references jsonb not null default '[]'::jsonb,
  expected_output jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.approvals (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete restrict,
  requested_by text not null,
  action_type text not null,
  reason text not null,
  status text not null check (status in ('pending', 'approved', 'rejected')),
  decided_by text,
  decision_note text,
  created_at timestamptz not null default now(),
  decided_at timestamptz
);

create index if not exists work_logs_project_created_at_idx
  on public.work_logs(project_id, created_at desc);
create index if not exists handoffs_project_created_at_idx
  on public.handoffs(project_id, created_at desc);
create index if not exists approvals_project_status_idx
  on public.approvals(project_id, status);

-- Default deny: the cloud gateway will use server-side credentials.
-- Do not add public policies. Add narrowly scoped authenticated policies only after
-- the approval and role design is tested.
alter table public.projects enable row level security;
alter table public.agents enable row level security;
alter table public.work_logs enable row level security;
alter table public.handoffs enable row level security;
alter table public.approvals enable row level security;
