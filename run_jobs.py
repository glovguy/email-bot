#!/usr/bin/env python3
"""
Job Runner Script

This script checks for and runs jobs that are due to be executed.
It should be run every minute by a cron job or similar scheduler.
"""

import logging
from src.models import setup_db
from src.job import Job

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('job_runner.log')
    ]
)

if __name__ == "__main__":
    # Ensure database is set up
    setup_db()
    # Run jobs
    Job.run_jobs() 