# Database Setup

PostgreSQL 17 running in Docker.

## Quick Start

### 1. Start PostgreSQL

```bash
# Start the database
docker-compose up -d

# Check that it's running
docker-compose ps

# View logs
docker-compose logs -f postgres
```

### 2. Connect to Database

```bash
# Using psql from the container
docker-compose exec postgres psql -U ltt_user -d ltt_dev

# Or connect from your local machine (if psql is installed)
psql postgresql://ltt_user:ltt_password@localhost:5432/ltt_dev
```

### 3. Stop PostgreSQL

```bash
# Stop the database (preserves data)
docker-compose stop

# Stop and remove container (preserves data in volume)
docker-compose down

# Stop and remove everything including data
docker-compose down -v
```

## Database Details

- **Host**: localhost
- **Port**: 5432
- **Database**: ltt_dev
- **User**: ltt_user
- **Password**: ltt_password

## Environment Variables

Copy `.env.example` to `.env` and adjust if needed:

```bash
cp .env.example .env
```

The default connection string:
```
postgresql://ltt_user:ltt_password@localhost:5432/ltt_dev
```

## Data Persistence

Data is stored in a Docker volume named `postgres_data`. This persists even when you stop or remove the container. To completely reset:

```bash
docker-compose down -v
docker-compose up -d
```

## Useful Commands

```bash
# List databases
docker-compose exec postgres psql -U ltt_user -l

# Execute SQL file
docker-compose exec -T postgres psql -U ltt_user -d ltt_dev < schema.sql

# Create database backup
docker-compose exec -T postgres pg_dump -U ltt_user ltt_dev > backup.sql

# Restore from backup
docker-compose exec -T postgres psql -U ltt_user -d ltt_dev < backup.sql
```
