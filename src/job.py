"""
Job management module

This module handles the scheduling and execution of background jobs.
"""

import logging
import datetime
from typing import Callable, Dict, Sequence

from sqlalchemy import Boolean, Column, Integer, String, DateTime, func

from src.skills.zettel import sync_local_docs
from src.models import Base, db_session
from src.skills.email.jobs import check_mailbox, send_next_message_if_bandwidth_available

# Configure logging
logger = logging.getLogger(__name__)

# Job registry - maps job identifiers to their functions
JOB_REGISTRY: Dict[str, Callable[[], None]] = {
    'check_mailbox': check_mailbox,
    'send_enqueued_messages': send_next_message_if_bandwidth_available,
    'sync_local_docs': sync_local_docs,
}

class Job(Base):
    """Model for storing scheduled jobs"""
    __tablename__ = 'jobs'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, unique=True, index=True)
    job_identifier = Column(String(255), nullable=False, index=True)
    interval_minutes = Column(Integer, nullable=False)
    last_run_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<Job {self.name}>"

    @classmethod
    def create(cls, name: str, job_identifier: str, interval_minutes: int) -> 'Job':
        """Create a new job"""
        if job_identifier not in JOB_REGISTRY:
            raise ValueError(f"Job identifier '{job_identifier}' not found in registry")
            
        job = cls(
            name=name,
            job_identifier=job_identifier,
            interval_minutes=interval_minutes
        )
        db_session.add(job)
        db_session.commit()
        return job

    @classmethod
    def get_due_jobs(cls) -> Sequence['Job']:
        """Get all jobs that are due to run"""
        now = datetime.datetime.now(datetime.UTC)
        return db_session.query(cls).filter(
            cls.is_active == True,
            (cls.last_run_at == None) | 
            (func.extract('epoch', now - cls.last_run_at) >= cls.interval_minutes * 60)
        ).all()

    @classmethod
    def run_jobs(cls) -> None:
        """Check for and run due jobs"""
        try:
            # Get all jobs that are due to run
            due_jobs = cls.get_due_jobs()
            if not due_jobs:
                logger.info("No jobs due to run at %s", datetime.datetime.now(datetime.UTC))
                return
            
            logger.info("Found %d jobs due to run", len(due_jobs))
            # Run each job
            for job in due_jobs:
                job.run()
        
        except Exception as e:
            logger.error("Error in job runner: %s", e)

    def run(self) -> bool:
        """Run the job and update last_run_at"""
        try:
            if self.job_identifier not in JOB_REGISTRY:
                logger.error("Job %s not found in registry", self.job_identifier)
                return False
                
            logger.info("Running job: %s", self.name)
            JOB_REGISTRY[self.job_identifier]()
            
            self.last_run_at = datetime.datetime.now(datetime.UTC)
            db_session.commit()
            logger.info("Job %s completed successfully", self.name)
            return True
            
        except Exception as e:
            logger.error("Job %s failed: %s", self.name, e)
            return False 