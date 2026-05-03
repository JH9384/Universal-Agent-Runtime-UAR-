#!/bin/bash
# Docker entrypoint script for UAR
# Validates environment before starting the application

set -e

echo "=== UAR Docker Entrypoint ==="

# Check if we can run Python validation
if ! python3 -c "from uar.config import validate_environment, validate_docker_environment; 
issues = validate_environment() + validate_docker_environment();
[print(f'ERROR: {i}') for i in issues];
exit(len(issues) > 0)" 2>/dev/null; then
    echo "ERROR: Environment validation failed"
    echo "Please check your configuration and try again"
    exit 1
fi

echo "Environment validation passed"

# Create required directories
mkdir -p /var/lib/uar/runs /var/log/uar

# Check permissions
if [ ! -w "/var/lib/uar" ]; then
    echo "ERROR: Cannot write to /var/lib/uar"
    exit 1
fi

if [ ! -w "/var/log/uar" ]; then
    echo "ERROR: Cannot write to /var/log/uar"
    exit 1
fi

echo "Starting UAR application..."

# Execute the main command
exec "$@"
