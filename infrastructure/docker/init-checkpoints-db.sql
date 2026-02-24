-- Creates the separate checkpoint database for LangGraph conversation state.
-- Mounted into /docker-entrypoint-initdb.d/ and runs on first container init.
CREATE DATABASE ltt_checkpoints;
GRANT ALL PRIVILEGES ON DATABASE ltt_checkpoints TO ltt_user;
