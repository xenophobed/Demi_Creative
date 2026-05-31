-- Runs once on first container boot via the pgvector image's
-- /docker-entrypoint-initdb.d/ hook. Makes the extension available
-- before the app's init_vector_schema() runs, so the app never has to
-- own a superuser-requiring DDL.
CREATE EXTENSION IF NOT EXISTS vector;
