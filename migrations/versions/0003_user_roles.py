"""Add the role of the user (applicant, analyst, admin)

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-14 12:10:00.000000

Every existing user becomes an applicant. The downgrade drops the column and its check.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('role', sa.String(length=20), server_default='applicant', nullable=False))
        batch_op.create_check_constraint('ck_users_role', "role IN ('applicant', 'analyst', 'admin')")


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_constraint('ck_users_role', type_='check')
        batch_op.drop_column('role')
