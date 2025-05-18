#!/bin/bash

# QueueMe Deployment Verification Script for Ubuntu 24.04
# ======================================================
# This script checks the status of all QueueMe components
# to ensure they are running correctly after deployment.

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=====================================================${NC}"
echo -e "${GREEN}      QueueMe Deployment Verification Script         ${NC}"
echo -e "${GREEN}=====================================================${NC}"

# Function to check the status of a service
check_service() {
    local service_name="$1"
    echo -e "\n${YELLOW}Checking ${service_name}...${NC}"

    if systemctl is-active --quiet "$service_name"; then
        echo -e "${GREEN}✓ $service_name is running${NC}"
        return 0
    else
        echo -e "${RED}✗ $service_name is not running${NC}"
        echo -e "  ${YELLOW}Status: $(systemctl status "$service_name" | grep "Active:" | sed 's/^[ \t]*//')${NC}"
        return 1
    fi
}

# Function to check a port
check_port() {
    local port="$1"
    local service_name="$2"
    echo -e "\n${YELLOW}Checking if port $port is open ($service_name)...${NC}"

    if nc -z localhost "$port"; then
        echo -e "${GREEN}✓ Port $port is open ($service_name)${NC}"
        return 0
    else
        echo -e "${RED}✗ Port $port is not open ($service_name)${NC}"
        return 1
    fi
}

# Function to check if a command exists
command_exists() {
    command -v "$1" &> /dev/null
}

# Create a results array
declare -a RESULTS

# 1. Check Operating System
echo -e "\n${YELLOW}Checking Operating System...${NC}"
OS_VERSION=$(lsb_release -d | cut -f2-)
if [[ "$OS_VERSION" == *"Ubuntu 24.04"* ]]; then
    echo -e "${GREEN}✓ Running on Ubuntu 24.04 LTS${NC}"
    RESULTS+=("Operating System: PASS")
else
    echo -e "${RED}✗ Not running on Ubuntu 24.04 LTS. Found: $OS_VERSION${NC}"
    RESULTS+=("Operating System: FAIL - Not Ubuntu 24.04 LTS")
fi

# 2. Check Python version
echo -e "\n${YELLOW}Checking Python version...${NC}"
PYTHON_VERSION=$(python3 --version)
if [[ "$PYTHON_VERSION" == *"Python 3.1"* ]] || [[ "$PYTHON_VERSION" == *"Python 3.2"* ]]; then
    echo -e "${GREEN}✓ Python version is compatible: $PYTHON_VERSION${NC}"
    RESULTS+=("Python Version: PASS - $PYTHON_VERSION")
else
    echo -e "${YELLOW}⚠ Python version might not be compatible: $PYTHON_VERSION${NC}"
    RESULTS+=("Python Version: WARNING - $PYTHON_VERSION")
fi

# 3. Check PostgreSQL
echo -e "\n${YELLOW}Checking PostgreSQL...${NC}"
if command_exists psql; then
    PG_VERSION=$(psql --version)
    echo -e "${GREEN}✓ PostgreSQL is installed: $PG_VERSION${NC}"

    if systemctl is-active --quiet postgresql; then
        echo -e "${GREEN}✓ PostgreSQL service is running${NC}"
        RESULTS+=("PostgreSQL: PASS - $PG_VERSION")

        # Check if the database exists
        if sudo -u postgres psql -lqt | cut -d \| -f 1 | grep -qw queueme; then
            echo -e "${GREEN}✓ QueueMe database exists${NC}"
            RESULTS+=("QueueMe Database: PASS")
        else
            echo -e "${RED}✗ QueueMe database does not exist${NC}"
            RESULTS+=("QueueMe Database: FAIL - Database not found")
        fi

        # Check PostGIS extension
        if sudo -u postgres psql -c "SELECT PostGIS_version();" queueme &>/dev/null; then
            echo -e "${GREEN}✓ PostGIS extension is installed${NC}"
            RESULTS+=("PostGIS Extension: PASS")
        else
            echo -e "${RED}✗ PostGIS extension is not installed${NC}"
            RESULTS+=("PostGIS Extension: FAIL - Not installed")
        fi
    else
        echo -e "${RED}✗ PostgreSQL service is not running${NC}"
        RESULTS+=("PostgreSQL Service: FAIL - Not running")
    fi
else
    echo -e "${RED}✗ PostgreSQL is not installed${NC}"
    RESULTS+=("PostgreSQL: FAIL - Not installed")
fi

# 4. Check Redis
echo -e "\n${YELLOW}Checking Redis...${NC}"
if command_exists redis-cli; then
    REDIS_VERSION=$(redis-cli --version)
    echo -e "${GREEN}✓ Redis client is installed: $REDIS_VERSION${NC}"

    if systemctl is-active --quiet redis-server; then
        echo -e "${GREEN}✓ Redis service is running${NC}"

        # Try to ping Redis
        if redis-cli ping 2>/dev/null | grep -q "PONG"; then
            echo -e "${GREEN}✓ Redis connection successful${NC}"
            RESULTS+=("Redis: PASS - $REDIS_VERSION")
        else
            echo -e "${RED}✗ Cannot connect to Redis${NC}"
            RESULTS+=("Redis Connection: FAIL - Cannot connect")
        fi
    else
        echo -e "${RED}✗ Redis service is not running${NC}"
        RESULTS+=("Redis Service: FAIL - Not running")
    fi
else
    echo -e "${RED}✗ Redis client is not installed${NC}"
    RESULTS+=("Redis: FAIL - Not installed")
fi

# 5. Check Nginx
echo -e "\n${YELLOW}Checking Nginx...${NC}"
if command_exists nginx; then
    NGINX_VERSION=$(nginx -v 2>&1)
    echo -e "${GREEN}✓ Nginx is installed: $NGINX_VERSION${NC}"

    if systemctl is-active --quiet nginx; then
        echo -e "${GREEN}✓ Nginx service is running${NC}"
        RESULTS+=("Nginx: PASS - $NGINX_VERSION")

        # Check if QueueMe site is enabled
        if [ -f /etc/nginx/sites-enabled/queueme ]; then
            echo -e "${GREEN}✓ QueueMe Nginx site is enabled${NC}"
            RESULTS+=("Nginx QueueMe Site: PASS")
        else
            echo -e "${RED}✗ QueueMe Nginx site is not enabled${NC}"
            RESULTS+=("Nginx QueueMe Site: FAIL - Not enabled")
        fi
    else
        echo -e "${RED}✗ Nginx service is not running${NC}"
        RESULTS+=("Nginx Service: FAIL - Not running")
    fi
else
    echo -e "${RED}✗ Nginx is not installed${NC}"
    RESULTS+=("Nginx: FAIL - Not installed")
fi

# 6. Check QueueMe services
echo -e "\n${YELLOW}Checking QueueMe services...${NC}"

# Check systemd services
services=("queueme" "queueme-daphne" "queueme-celery" "queueme-celery-beat")
for service in "${services[@]}"; do
    check_service "$service"
    if [ $? -eq 0 ]; then
        RESULTS+=("$service Service: PASS")
    else
        RESULTS+=("$service Service: FAIL - Not running")
    fi
done

# 7. Check ports
echo -e "\n${YELLOW}Checking ports...${NC}"
ports=("80:Nginx" "8000:Gunicorn" "8001:Daphne" "5432:PostgreSQL" "6379:Redis")
for port_info in "${ports[@]}"; do
    port=$(echo "$port_info" | cut -d: -f1)
    service=$(echo "$port_info" | cut -d: -f2)
    check_port "$port" "$service"
    if [ $? -eq 0 ]; then
        RESULTS+=("Port $port ($service): PASS")
    else
        RESULTS+=("Port $port ($service): FAIL - Not open")
    fi
done

# 8. Check Django application
echo -e "\n${YELLOW}Checking Django application...${NC}"
SITE_URL="http://localhost"

if command_exists curl; then
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$SITE_URL")
    if [ "$HTTP_CODE" -eq 200 ]; then
        echo -e "${GREEN}✓ Django application is responding (HTTP 200)${NC}"
        RESULTS+=("Django Application: PASS - HTTP 200")
    else
        echo -e "${RED}✗ Django application returned HTTP $HTTP_CODE${NC}"
        RESULTS+=("Django Application: FAIL - HTTP $HTTP_CODE")
    fi
else
    echo -e "${YELLOW}⚠ Curl is not installed, cannot check Django application${NC}"
    RESULTS+=("Django Application: UNKNOWN - curl not installed")
fi

# 9. Summary
echo -e "\n${GREEN}=====================================================${NC}"
echo -e "${GREEN}                  Summary Report                     ${NC}"
echo -e "${GREEN}=====================================================${NC}"

PASS_COUNT=0
FAIL_COUNT=0
WARNING_COUNT=0
UNKNOWN_COUNT=0

for result in "${RESULTS[@]}"; do
    if [[ "$result" == *"PASS"* ]]; then
        echo -e "${GREEN}$result${NC}"
        ((PASS_COUNT++))
    elif [[ "$result" == *"FAIL"* ]]; then
        echo -e "${RED}$result${NC}"
        ((FAIL_COUNT++))
    elif [[ "$result" == *"WARNING"* ]]; then
        echo -e "${YELLOW}$result${NC}"
        ((WARNING_COUNT++))
    else
        echo -e "${YELLOW}$result${NC}"
        ((UNKNOWN_COUNT++))
    fi
done

echo -e "\n${GREEN}=====================================================${NC}"
echo -e "PASS: $PASS_COUNT | FAIL: $FAIL_COUNT | WARNING: $WARNING_COUNT | UNKNOWN: $UNKNOWN_COUNT"

if [ $FAIL_COUNT -gt 0 ]; then
    echo -e "${RED}There are issues with the deployment that need to be fixed.${NC}"
    exit 1
elif [ $WARNING_COUNT -gt 0 ]; then
    echo -e "${YELLOW}Deployment is working but there are warnings to address.${NC}"
    exit 0
else
    echo -e "${GREEN}Deployment verification completed successfully!${NC}"
    exit 0
fi
