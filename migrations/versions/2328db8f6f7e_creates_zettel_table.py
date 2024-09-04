"""Creates zettel table

Revision ID: 2328db8f6f7e
Revises: b36d609a3300
Create Date: 2024-09-02 18:10:30.381809

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2328db8f6f7e'
down_revision = 'b36d609a3300'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('zettel',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('uuid', sa.String(length=512), nullable=False),
    sa.Column('sha', sa.String(length=512), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('title', sa.Text(), nullable=False),
    sa.Column('filepath', sa.Text(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('zettel')
    # ### end Alembic commands ###