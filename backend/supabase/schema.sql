-- Supabase SQL Editor에서 검토 후 실행하세요.
create type public.quote_status as enum ('review_required','confirmed','rejected','archived','extracting');
create table public.quotes (
 id uuid primary key default gen_random_uuid(), quote_number text, title text,
 issuer_company text, customer_name text, contact_name text, contact_email text, contact_phone text,
 issue_date date, valid_until date, delivery_date date, subtotal numeric(18,4), tax_amount numeric(18,4),
 total_amount numeric(18,4), currency text not null default 'KRW', discount_terms text, payment_terms text,
 delivery_terms text, status public.quote_status not null default 'review_required',
 source_filename text, source_storage_path text, extraction_raw jsonb, review_note text,
 created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
create table public.quote_items (
 id uuid primary key default gen_random_uuid(), quote_id uuid not null references public.quotes(id) on delete cascade,
 line_number integer, item_name text not null, item_name_original text, specification text, unit text,
 quantity numeric(18,4), unit_price numeric(18,4), amount numeric(18,4), currency text not null default 'KRW',
 raw_fields jsonb, created_at timestamptz not null default now()
);
create index quotes_customer_idx on public.quotes(customer_name);
create index quotes_date_idx on public.quotes(issue_date desc);
create index quotes_status_idx on public.quotes(status);
-- RLS는 인증/조직별 권한 정책 결정 후 별도 설정하세요.
