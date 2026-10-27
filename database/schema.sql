-- FinLife schema (PostgreSQL / Supabase). Run once in Supabase > SQL Editor.
-- Safe to re-run: uses IF NOT EXISTS / DROP POLICY IF EXISTS.
-- Requires PostgreSQL 15+ (Supabase default) for ON DELETE SET NULL (column).

create extension if not exists pgcrypto;

-- ---------- helpers ----------
create or replace function public.set_updated_at() returns trigger
language plpgsql as $$ begin new.updated_at = now(); return new; end $$;

-- ---------- profiles ----------
create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  full_name text,
  preferred_currency text not null default 'INR' check (preferred_currency in ('INR','USD','EUR','GBP')),
  preferred_theme text not null default 'system' check (preferred_theme in ('light','dark','system')),
  alloc_needs numeric(5,2) not null default 50 check (alloc_needs between 0 and 100),
  alloc_wants numeric(5,2) not null default 30 check (alloc_wants between 0 and 100),
  alloc_savings numeric(5,2) not null default 20 check (alloc_savings between 0 and 100),
  seeded boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- ---------- accounts ----------
create table if not exists public.accounts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  account_name text not null,
  account_type text not null default 'bank'
    check (account_type in ('bank','cash','wallet','credit_card','investment','other')),
  opening_balance numeric(14,2) not null default 0,
  currency text not null default 'INR',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (id, user_id),
  unique (user_id, account_name)
);

-- ---------- categories ----------
create table if not exists public.categories (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade,  -- NULL only for explicit system categories (none are seeded)
  name text not null,
  parent_category_id uuid,
  financial_classification text not null
    check (financial_classification in ('need','want','income','saving','investment')),
  is_essential boolean not null default false,
  is_default boolean not null default false,
  created_at timestamptz not null default now(),
  unique (id, user_id),
  foreign key (parent_category_id, user_id) references public.categories(id, user_id)
    on delete set null (parent_category_id)
);
create unique index if not exists categories_unique_name
  on public.categories (user_id, lower(name), coalesce(parent_category_id, '00000000-0000-0000-0000-000000000000'::uuid));

-- ---------- transactions ----------
-- Composite foreign keys (id, user_id) make it impossible to reference another user's
-- account or category, even if a client sends a forged id.
create table if not exists public.transactions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  account_id uuid not null,
  category_id uuid,
  transaction_type text not null
    check (transaction_type in ('income','expense','investment','transfer_in','transfer_out','refund')),
  description text not null default '',
  amount numeric(14,2) not null check (amount > 0),
  transaction_date date not null default current_date,
  payment_method text not null default 'Other'
    check (payment_method in ('UPI','Cash','Debit card','Credit card','Bank transfer','Other')),
  notes text,
  is_essential boolean,                -- NULL = use the category's classification
  transfer_group_id uuid,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  foreign key (account_id, user_id) references public.accounts(id, user_id) on delete restrict,
  foreign key (category_id, user_id) references public.categories(id, user_id) on delete set null (category_id)
);
create index if not exists tx_user_date on public.transactions (user_id, transaction_date desc);
create index if not exists tx_transfer_group on public.transactions (transfer_group_id) where transfer_group_id is not null;

-- ---------- budgets ----------
create table if not exists public.budgets (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  category_id uuid not null,
  period text not null default 'monthly' check (period = 'monthly'),
  budget_amount numeric(14,2) not null check (budget_amount > 0),
  warning_thresholds integer[] not null default '{75,90,100}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, category_id, period),
  foreign key (category_id, user_id) references public.categories(id, user_id) on delete cascade
);

-- ---------- goals ----------
create table if not exists public.financial_goals (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  goal_name text not null,
  goal_type text not null default 'other'
    check (goal_type in ('car','house','emergency_fund','education','travel','purchase','retirement','other')),
  target_amount numeric(14,2) not null check (target_amount > 0),
  current_allocated_amount numeric(14,2) not null default 0 check (current_allocated_amount >= 0), -- amount already set aside before tracking here
  target_date date not null,
  priority text not null default 'medium' check (priority in ('high','medium','low')),
  inflation_assumption numeric(5,2) not null default 0 check (inflation_assumption between 0 and 50), -- % per year
  status text not null default 'active' check (status in ('active','completed','paused','cancelled')),
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (id, user_id)
);

create table if not exists public.goal_contributions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  goal_id uuid not null,
  amount numeric(14,2) not null check (amount <> 0),   -- negative = withdrawal from the goal
  contribution_date date not null default current_date,
  source text,
  notes text,
  created_at timestamptz not null default now(),
  foreign key (goal_id, user_id) references public.financial_goals(id, user_id) on delete cascade
);

create table if not exists public.investment_plans (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  goal_id uuid,
  plan_name text not null default 'Scenario',
  initial_amount numeric(14,2) not null default 0 check (initial_amount >= 0),
  monthly_contribution numeric(14,2) not null default 0 check (monthly_contribution >= 0),
  investment_horizon numeric(5,2) not null check (investment_horizon > 0),   -- years
  risk_profile text not null default 'moderate' check (risk_profile in ('conservative','moderate','aggressive')),
  return_assumption numeric(5,2) not null,     -- middle scenario, % per year
  low_return numeric(5,2),
  high_return numeric(5,2),
  fee_assumption numeric(5,2) not null default 0,
  created_at timestamptz not null default now(),
  foreign key (goal_id, user_id) references public.financial_goals(id, user_id) on delete set null (goal_id)
);

-- One row per valuation. The latest row per (record_type, name) is the current value;
-- older rows form the net-worth history.
create table if not exists public.assets_and_liabilities (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  record_type text not null check (record_type in ('asset','liability')),
  name text not null,
  category text not null,
  current_value numeric(14,2) not null check (current_value >= 0),
  valuation_date date not null default current_date,
  notes text,
  created_at timestamptz not null default now()
);

create table if not exists public.recurring_transactions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  description text not null,
  transaction_type text not null default 'expense' check (transaction_type in ('income','expense','investment')),
  amount numeric(14,2) not null check (amount > 0),
  category_id uuid,
  account_id uuid not null,
  payment_method text not null default 'Other',
  frequency text not null default 'monthly' check (frequency in ('weekly','monthly','quarterly','yearly')),
  next_due_date date not null,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  foreign key (account_id, user_id) references public.accounts(id, user_id) on delete cascade,
  foreign key (category_id, user_id) references public.categories(id, user_id) on delete set null (category_id)
);

-- ---------- updated_at triggers ----------
do $$ declare t text; begin
  foreach t in array array['profiles','accounts','transactions','budgets','financial_goals'] loop
    execute format('drop trigger if exists trg_%1$s_updated on public.%1$s', t);
    execute format('create trigger trg_%1$s_updated before update on public.%1$s for each row execute function public.set_updated_at()', t);
  end loop;
end $$;

-- ---------- profile auto-creation on signup ----------
create or replace function public.handle_new_user() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (id, full_name)
  values (new.id, coalesce(new.raw_user_meta_data->>'full_name', new.raw_user_meta_data->>'name', ''))
  on conflict (id) do nothing;
  return new;
end $$;
drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created after insert on auth.users
  for each row execute function public.handle_new_user();

-- ---------- Row Level Security ----------
do $$ declare t text; begin
  foreach t in array array['accounts','categories','transactions','budgets','financial_goals',
      'goal_contributions','investment_plans','assets_and_liabilities','recurring_transactions'] loop
    execute format('alter table public.%I enable row level security', t);
    execute format('alter table public.%I force row level security', t);
    execute format('drop policy if exists "owner_all" on public.%I', t);
    execute format($p$create policy "owner_all" on public.%I for all to authenticated
       using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()))$p$, t);
  end loop;
end $$;

alter table public.profiles enable row level security;
alter table public.profiles force row level security;
drop policy if exists "profile_select" on public.profiles;
drop policy if exists "profile_insert" on public.profiles;
drop policy if exists "profile_update" on public.profiles;
create policy "profile_select" on public.profiles for select to authenticated using (id = (select auth.uid()));
create policy "profile_insert" on public.profiles for insert to authenticated with check (id = (select auth.uid()));
create policy "profile_update" on public.profiles for update to authenticated
  using (id = (select auth.uid())) with check (id = (select auth.uid()));

-- Anonymous (logged-out) API callers get no access to any application table.
revoke all on all tables in schema public from anon;
