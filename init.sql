-- Initial database setup for Learning Task Tracker
-- This file runs automatically when the container is first created

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Set timezone
SET timezone = 'UTC';

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE ltt_dev TO ltt_user;
