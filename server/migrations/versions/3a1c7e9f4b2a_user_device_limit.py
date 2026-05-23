"""user device_limit override

Revision ID: 3a1c7e9f4b2a
Revises: dbff099ad682
Create Date: 2026-05-23 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '3a1c7e9f4b2a'
down_revision = 'dbff099ad682'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('device_limit', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('users', 'device_limit')
