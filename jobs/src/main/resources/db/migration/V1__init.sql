-- Job tables: written ONLY by the Python worker, read by the API.
create table sources (
    id          bigint generated always as identity primary key,
    key         text        not null unique,
    type        text        not null,
    config_json jsonb       not null default '{}'::jsonb,
    enabled     boolean     not null default true
);

create table jobs (
    id               uuid primary key default gen_random_uuid(),
    source_id        bigint      not null references sources (id),
    external_id      text        not null,
    title            text        not null,
    company          text        not null,
    location_raw     text        not null default '',
    description_text text        not null default '',
    apply_url        text        not null,
    posted_at        timestamptz,
    first_seen_at    timestamptz not null default now(),
    last_seen_at     timestamptz not null default now(),
    is_active        boolean     not null default true,
    content_hash     text        not null,
    dedupe_key       text        not null,
    canonical_job_id uuid references jobs (id) on delete set null,
    constraint uq_jobs_source_external unique (source_id, external_id)
);

create index idx_jobs_active on jobs (is_active);
create index idx_jobs_dedupe_key on jobs (dedupe_key);
create index idx_jobs_listing on jobs (coalesce(posted_at, first_seen_at) desc)
    where is_active and canonical_job_id is null;
create index idx_jobs_fts on jobs using gin (
    to_tsvector('english', title || ' ' || company || ' ' || description_text)
);

create table job_tags (
    job_id           uuid primary key references jobs (id) on delete cascade,
    role_category    text        not null,
    role_title_clean text        not null,
    city             text        not null,
    state            text,
    work_mode        text        not null check (work_mode in ('onsite', 'hybrid', 'remote')),
    job_type         text        not null check (job_type in ('internship', 'full_time', 'contract')),
    experience_min   integer,
    experience_max   integer,
    is_fresher       boolean     not null,
    model            text        not null,
    prompt_version   text        not null,
    input_tokens     integer     not null default 0,
    output_tokens    integer     not null default 0,
    tagged_at        timestamptz not null default now()
);

create index idx_job_tags_filter on job_tags (role_category, city, work_mode);

create table ingest_runs (
    id           bigint generated always as identity primary key,
    started_at   timestamptz    not null default now(),
    finished_at  timestamptz,
    fetched      integer        not null default 0,
    new          integer        not null default 0,
    updated      integer        not null default 0,
    deactivated  integer        not null default 0,
    tagged       integer        not null default 0,
    llm_cost_usd numeric(12, 6) not null default 0,
    errors_json  jsonb          not null default '[]'::jsonb
);

-- User tables: written ONLY by the Spring Boot API.
create table users (
    id             uuid primary key default gen_random_uuid(),
    email          text        not null unique,
    password_hash  text,
    name           text        not null,
    provider       text        not null default 'local',
    provider_id    text,
    email_verified boolean     not null default false,
    created_at     timestamptz not null default now()
);

create table saved_jobs (
    user_id    uuid        not null references users (id) on delete cascade,
    job_id     uuid        not null references jobs (id) on delete cascade,
    created_at timestamptz not null default now(),
    primary key (user_id, job_id)
);

create table apply_clicks (
    id         bigint generated always as identity primary key,
    user_id    uuid references users (id) on delete set null,
    job_id     uuid        not null references jobs (id) on delete cascade,
    clicked_at timestamptz not null default now()
);

create index idx_apply_clicks_user on apply_clicks (user_id, clicked_at desc);
