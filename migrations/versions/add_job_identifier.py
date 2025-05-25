"""Add job_identifier column to jobs table

Revision ID: add_job_identifier
Revises: add_job_model
Create Date: 2024-04-27 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_job_identifier'
down_revision = "add_job_model"
branch_labels = None
depends_on = None

def upgrade():
    # Add job_identifier column
    op.add_column('jobs', sa.Column('job_identifier', sa.String(length=255), nullable=True))
    
    # Copy name to job_identifier for existing records
    op.execute("UPDATE jobs SET job_identifier = name")
    
    # Make job_identifier not nullable after data migration
    op.alter_column('jobs', 'job_identifier', nullable=False)
    
    # Drop module and function columns as they're no longer needed
    op.drop_column('jobs', 'module')
    op.drop_column('jobs', 'function')

def downgrade():
    # Add back module and function columns
    op.add_column('jobs', sa.Column('module', sa.String(length=255), nullable=True))
    op.add_column('jobs', sa.Column('function', sa.String(length=255), nullable=True))
    
    # Drop job_identifier column
    op.drop_column('jobs', 'job_identifier') 