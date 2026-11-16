-- Optional hardening: run the API with a role that can only READ the job tables.
-- Run once as the database owner, after the first Flyway migration.
-- Then give the API:   SPRING_DATASOURCE_USERNAME=jobs_api  (+ its password)
--                      SPRING_FLYWAY_USER=<owner> / SPRING_FLYWAY_PASSWORD=<owner password>
-- and keep using the owner (or a third role) as the worker's DATABASE_URL user.

create role jobs_api login password 'CHANGE_ME';

grant usage on schema public to jobs_api;

-- job tables: read only (the Python worker is their only writer)
grant select on sources, jobs, job_tags, ingest_runs to jobs_api;

-- user tables: the API is their only writer
grant select, insert, update, delete on users, saved_jobs, apply_clicks,
      spring_session, spring_session_attributes to jobs_api;
grant usage, select on all sequences in schema public to jobs_api;

-- Flyway's history table is read at startup when the API validates the schema.
grant select on flyway_schema_history to jobs_api;
