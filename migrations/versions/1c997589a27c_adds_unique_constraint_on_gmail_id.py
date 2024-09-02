"""Adds unique constraint on gmail_id

Revision ID: 1c997589a27c
Revises: 85088065311a
Create Date: 2024-08-31 15:52:56.751179

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1c997589a27c'
down_revision = '85088065311a'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_unique_constraint(None, 'emails', ['gmail_id'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'emails', type_='unique')
    # ### end Alembic commands ###