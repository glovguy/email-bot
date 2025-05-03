#!/usr/bin/env python3
"""
Job Runner Script

This script checks for and runs jobs that are due to be executed.
It should be run every minute by a cron job or similar scheduler.
"""

import sys
import os
import logging
import datetime

# Add the parent directory to the path so we can import from src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models import Job, db_session
from src.skills.email.oauth_credential import *
from src.skills.persona import *
from src.skills.email import *
from src.skills.zettel import *
from src.skills.interest import *
from src.skills.social_stockfish.models import *

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('job_runner.log')
    ]
)
logger = logging.getLogger('job_runner')

# move to a classmethod on Job model?
def run_jobs():
    """Check for and run due jobs"""
    try:
        # Get all jobs that are due to run
        due_jobs = Job.get_due_jobs()
        if not due_jobs:
            logger.info("No jobs due to run at %s", datetime.datetime.now(datetime.UTC))
            return
        
        logger.info("Found %d jobs due to run", len(due_jobs))
        # Run each job
        for job in due_jobs:
            logger.info("Running job: %s", job.name)
            success = job.run()
            
            if success:
                logger.info("Job %s completed successfully", job.name)
            else:
                logger.error("Job %s failed", job.name)
    
    except Exception as e:
        logger.error("Error in job runner: %s", e)
    finally:
        # Always close the session
        db_session.remove()

if __name__ == "__main__":
    run_jobs()
