\set ON_ERROR_STOP on
\getenv esus_leitura_pass ESUS_LEITURA_PASS

SELECT format(
    'CREATE ROLE esus_leitura LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT PASSWORD %L',
    :'esus_leitura_pass'
)
WHERE NOT EXISTS (
    SELECT 1
    FROM pg_roles
    WHERE rolname = 'esus_leitura'
) \gexec

ALTER ROLE esus_leitura
    LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT
    PASSWORD :'esus_leitura_pass';

GRANT CONNECT ON DATABASE :"DBNAME" TO esus_leitura;
GRANT USAGE ON SCHEMA public TO esus_leitura;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO esus_leitura;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO esus_leitura;
