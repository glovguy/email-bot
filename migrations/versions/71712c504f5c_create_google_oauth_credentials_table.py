"""Create Google OAuth credentials table

Revision ID: 71712c504f5c
Revises: 2f5bd7cabc39
Create Date: 2024-08-21 21:27:49.280937

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '71712c504f5c'
down_revision = '2f5bd7cabc39'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('oauth_credential',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('token', sa.Text(), nullable=False),
    sa.Column('refresh_token', sa.String(length=512), nullable=True),
    sa.Column('token_uri', sa.String(length=512), nullable=False),
    sa.Column('client_id', sa.String(length=512), nullable=False),
    sa.Column('client_secret', sa.String(length=512), nullable=False),
    sa.Column('scopes', sa.Text(), nullable=True),
    sa.Column('expiry', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id')
    )
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('email_address', sa.String(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('signatures_csv', sa.String(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email_address')
    )
    op.create_table('emails',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('sender', sa.String(), nullable=False),
    sa.Column('recipients_csv', sa.String(), nullable=False),
    sa.Column('subject', sa.String(), nullable=False),
    sa.Column('content', sa.String(), nullable=False),
    sa.Column('timestamp', sa.DateTime(), nullable=False),
    sa.Column('thread_path', sa.String(), nullable=True),
    sa.Column('uid', sa.String(), nullable=True),
    sa.Column('message_id', sa.String(), nullable=True),
    sa.Column('sender_user_id', sa.Integer(), nullable=True),
    sa.Column('is_processed', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['sender_user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('emails')
    op.drop_table('users')
    op.drop_table('oauth_credential')
    # ### end Alembic commands ###
