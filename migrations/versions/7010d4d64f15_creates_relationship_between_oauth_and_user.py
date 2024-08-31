"""Creates relationship between oauth and user

Revision ID: 7010d4d64f15
Revises: 901ec8670b4a
Create Date: 2024-08-24 17:50:42.744701

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7010d4d64f15'
down_revision = '901ec8670b4a'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_foreign_key(None, 'oauth_credential', 'users', ['user_id'], ['id'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'oauth_credential', type_='foreignkey')
    # ### end Alembic commands ###