#!/bin/bash
# Ensure the output directory exists and is owned by crew_user so they can write files
mkdir -p /app/generated_projects
chown -R crew_user:crew_user /app/generated_projects

# Disable flutter analytics as the correct user
runuser -u crew_user -- flutter config --no-analytics >/dev/null 2>&1 || true

# Run the application as crew_user, preserving environment variables
exec runuser -u crew_user -- python3 main.py
