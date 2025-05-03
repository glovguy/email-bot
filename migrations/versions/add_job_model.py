"""Add Job model for async task management

Revision ID: add_job_model
Revises: af2cee72f120
Create Date: 2024-04-27 16:50:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_job_model'
down_revision = "af2cee72f120"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('module', sa.String(length=255), nullable=False),
        sa.Column('function', sa.String(length=255), nullable=False),
        sa.Column('interval_minutes', sa.Integer(), nullable=False),
        sa.Column('last_run_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    op.create_index('ix_jobs_name', 'jobs', ['name'], unique=True)

def downgrade():
    op.drop_index('ix_jobs_name', table_name='jobs')
    op.drop_table('jobs') 