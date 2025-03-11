"""creates contacts table and app_settings table

Revision ID: af2cee72f120
Revises: 717d4aec36cf
Create Date: 2025-03-09 16:45:35.409081

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime, timezone


# revision identifiers, used by Alembic.
revision = 'af2cee72f120'
down_revision = '717d4aec36cf'
branch_labels = None
depends_on = None


def upgrade():
    # Create contacts table
    op.create_table('contacts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('identifier', sa.String(length=255), nullable=False),
        sa.Column('identifier_type', sa.String(length=50), nullable=False),
        sa.Column('normalized_identifier', sa.String(length=255), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=lambda: datetime.now(timezone.utc)),
        sa.Column('updated_at', sa.DateTime(), default=lambda: datetime.now(timezone.utc)),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for contacts table
    op.create_index(op.f('ix_contacts_identifier'), 'contacts', ['identifier'], unique=False)
    op.create_index(op.f('ix_contacts_normalized_identifier'), 'contacts', ['normalized_identifier'], unique=False)
    
    # Create app_settings table
    op.create_table('app_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(length=255), nullable=False),
        sa.Column('value', sa.Text(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=lambda: datetime.now(timezone.utc)),
        sa.Column('updated_at', sa.DateTime(), default=lambda: datetime.now(timezone.utc)),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create index for app_settings
    op.create_index(op.f('ix_app_settings_key'), 'app_settings', ['key'], unique=True)


def downgrade():
    # Drop the tables in reverse order (to preserve referential integrity)
    op.drop_index(op.f('ix_app_settings_key'), table_name='app_settings')
    op.drop_table('app_settings')
    
    op.drop_index(op.f('ix_contacts_normalized_identifier'), table_name='contacts')
    op.drop_index(op.f('ix_contacts_identifier'), table_name='contacts')
    op.drop_table('contacts')
