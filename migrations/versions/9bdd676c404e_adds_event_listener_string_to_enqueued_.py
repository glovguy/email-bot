"""Adds event_listener string to enqueued_message model

Revision ID: 9bdd676c404e
Revises: 09c02c046c81
Create Date: 2024-10-11 19:09:28.873995

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9bdd676c404e'
down_revision = '09c02c046c81'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('enqueued_messages', sa.Column('response_listener', sa.String(length=255), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('enqueued_messages', 'response_listener')
    # ### end Alembic commands ###
