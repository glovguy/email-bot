#!/usr/bin/env python3
"""
Job Runner Script

This script checks for and runs jobs that are due to be executed.
It should be run every minute by a cron job or similar scheduler.
"""

import logging
from src.models import setup_db, db_session
from src.job import Job

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('job_runner.log')
    ]
)

if __name__ == "__main__":
    setup_db()
    Job.run_jobs()
    # job1 = db_session.query(Job).filter(Job.name == "check_mailbox").first()
    # job1.run()
    job2 = db_session.query(Job).filter(Job.name == "send_enqueued_messages").first()
    if job2:
        job2.run()