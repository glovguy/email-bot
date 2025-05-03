#!/usr/bin/env python3
"""
Job Migration Script

This script migrates existing jobs from app.config['JOBS'] to the new Job model.
"""

import sys
import os


# Add the parent directory to the path so we can import from src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models import *
from src.skills.persona import *
from src.skills.email import *
from src.skills.email.oauth_credential import *
from src.skills.zettel import *
from src.skills.interest import *
from src.skills.social_stockfish.models import *

jobs_config = [
    {
        'id': 'check_mailbox',
        'func': 'app:sync_mailbox',
        'trigger': 'interval',
        'minutes': 17
    },
    {
        'id': 'send_enqueued_messages',
        'func': 'app:send_enqueued_messages',
        'trigger': 'interval',
        'minutes': 29
    },
    {
        'id': 'sync_local_docs',
        'func': 'app:sync_local_docs',
        'trigger': 'interval',
        'days': 1
    },
    {
        'id': 'ponder_wittgenstein',
        'func': 'app:ponder_wittgenstein',
        'trigger': 'interval',
        'days': 2
    },
    {
        'id': 'ask_get_to_know_you',
        'func': 'app:ask_get_to_know_you',
        'trigger': 'interval',
        'days': 1
    }
]

def migrate_jobs():
    """Migrate jobs from app.config['JOBS'] to the Job model"""
    # Get the jobs from app.config
    jobs = jobs_config
    
    print(f"Found {len(jobs)} jobs to migrate")
    
    # Migrate each job
    for job_config in jobs:
        job_id = job_config.get('id')
        func_str = job_config.get('func')
        trigger = job_config.get('trigger')
        
        # Skip if not an interval job
        if trigger != 'interval':
            print(f"Skipping job {job_id} with trigger {trigger}")
            continue
        
        # Parse the function string (e.g., 'app:sync_mailbox')
        module_name, function_name = func_str.split(':')
        
        # Get the interval in minutes
        interval_minutes = job_config.get('minutes', 0)
        if 'days' in job_config:
            interval_minutes = job_config.get('days') * 24 * 60
        
        # Check if job already exists
        existing_job = db_session.query(Job).filter(Job.name == job_id).first()
        
        if existing_job:
            print(f"Job {job_id} already exists, updating...")
            existing_job.module = module_name
            existing_job.function = function_name
            existing_job.interval_minutes = interval_minutes
            existing_job.is_active = True
        else:
            print(f"Creating new job {job_id}...")
            Job.create(
                name=job_id,
                module=module_name,
                function=function_name,
                interval_minutes=interval_minutes
            )
    
    db_session.commit()
    print("Job migration complete")

if __name__ == "__main__":
    migrate_jobs()
