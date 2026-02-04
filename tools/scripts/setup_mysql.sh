#!/bin/bash
# Setup MySQL database for the Maji Ndogo water services project
# This script starts the MySQL container and ingests the SQL data

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
SQL_FILE="$PROJECT_ROOT/content/projects/DA/MN_Part1/MD_water_services_stu_v2.sql"

echo "=== MySQL Setup for Maji Ndogo Water Services ==="

# Check if SQL file exists
if [ ! -f "$SQL_FILE" ]; then
    echo "Error: SQL file not found at $SQL_FILE"
    exit 1
fi

# Start MySQL container
echo "Starting MySQL container..."
cd "$PROJECT_ROOT"
docker-compose up -d mysql

# Wait for MySQL to be ready
echo "Waiting for MySQL to be ready..."
until docker-compose exec -T mysql mysqladmin ping -h localhost -u root -proot_password --silent 2>/dev/null; do
    sleep 2
    echo "  Still waiting..."
done
echo "MySQL is ready!"

# Check if database already has data
TABLES=$(docker-compose exec -T mysql mysql -u learner -plearner_password md_water_services -e "SHOW TABLES;" 2>/dev/null | tail -n +2 | wc -l)

if [ "$TABLES" -gt 0 ]; then
    echo "Database already contains $TABLES tables."
    read -p "Do you want to reinitialize the database? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Keeping existing data."
        echo ""
        echo "=== Database Ready ==="
        echo "Connection details:"
        echo "  Host: localhost"
        echo "  Port: 3306"
        echo "  Database: md_water_services"
        echo "  User: learner"
        echo "  Password: learner_password"
        exit 0
    fi
fi

# Ingest SQL file
echo "Ingesting SQL data..."
docker-compose exec -T mysql mysql -u root -proot_password < "$SQL_FILE" 2>/dev/null

# Verify ingestion
echo ""
echo "Verifying data..."
docker-compose exec -T mysql mysql -u learner -plearner_password md_water_services -e "
SELECT 'Tables' as metric, COUNT(*) as count FROM information_schema.tables WHERE table_schema='md_water_services'
UNION ALL
SELECT 'Visits', COUNT(*) FROM visits
UNION ALL
SELECT 'Water Sources', COUNT(*) FROM water_source
UNION ALL
SELECT 'Employees', COUNT(*) FROM employee;
" 2>/dev/null

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Connection details:"
echo "  Host: localhost"
echo "  Port: 3306"
echo "  Database: md_water_services"
echo "  User: learner"
echo "  Password: learner_password"
echo ""
echo "To connect with MySQL Workbench:"
echo "  1. Open MySQL Workbench"
echo "  2. Create new connection with above details"
echo "  3. Test connection and save"
echo ""
echo "To connect via command line:"
echo "  docker-compose exec mysql mysql -u learner -plearner_password md_water_services"
