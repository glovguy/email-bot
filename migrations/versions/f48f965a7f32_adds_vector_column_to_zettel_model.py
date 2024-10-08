"""Adds vector column to zettel model

Revision ID: f48f965a7f32
Revises: 2328db8f6f7e
Create Date: 2024-09-03 22:01:34.067477

"""
from alembic import op
import sqlalchemy as sa
import src


# revision identifiers, used by Alembic.
revision = 'f48f965a7f32'
down_revision = '2328db8f6f7e'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('zettel', sa.Column('instructor_base_embedding', src.models.Vector(768), nullable=True))
    op.execute('ALTER TABLE zettel ALTER COLUMN uuid TYPE uuid USING uuid::uuid')
    op.alter_column('zettel', 'uuid', existing_type=sa.dialects.postgresql.UUID(as_uuid=True), nullable=False)
    op.alter_column('zettel', 'sha',
               existing_type=sa.VARCHAR(length=512),
               type_=sa.String(length=64),
               existing_nullable=False)
    op.alter_column('zettel', 'title',
               existing_type=sa.TEXT(),
               type_=sa.String(length=255),
               existing_nullable=False)
    op.alter_column('zettel', 'filepath',
               existing_type=sa.TEXT(),
               type_=sa.String(length=255),
               existing_nullable=False)
    op.create_index('ix_zettel_embedding', 'zettel', ['instructor_base_embedding'], unique=False, postgresql_using='ivfflat')
    op.create_unique_constraint(None, 'zettel', ['filepath'])
    op.create_unique_constraint(None, 'zettel', ['uuid'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'zettel', type_='unique')
    op.drop_constraint(None, 'zettel', type_='unique')
    op.drop_index('ix_zettel_embedding', table_name='zettel', postgresql_using='ivfflat')
    op.alter_column('zettel', 'filepath',
               existing_type=sa.String(length=255),
               type_=sa.TEXT(),
               existing_nullable=False)
    op.alter_column('zettel', 'title',
               existing_type=sa.String(length=255),
               type_=sa.TEXT(),
               existing_nullable=False)
    op.alter_column('zettel', 'sha',
               existing_type=sa.String(length=64),
               type_=sa.VARCHAR(length=512),
               existing_nullable=False)
    op.alter_column('zettel', 'uuid', existing_type=sa.dialects.postgresql.UUID(as_uuid=True), type_=sa.VARCHAR(), nullable=False)
    op.drop_column('zettel', 'instructor_base_embedding')
    # ### end Alembic commands ###
