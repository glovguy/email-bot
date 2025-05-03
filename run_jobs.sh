#!/bin/bash
# Job Runner Script
# This script runs the job runner every minute

# Get the directory of this script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Run the job runner with -B flag to disable bytecode caching
PYTHONDONTWRITEBYTECODE=1 python3 -B "$DIR/src/jobs.py"

# Sleep for 60 seconds
sleep 60

# Run this script again
exec "$0"