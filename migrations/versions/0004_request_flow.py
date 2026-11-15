"""Request flow: status and outcome of credit applications, reviews and the inference log

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-15 18:30:00.000000

Existing applications become Pending without an outcome. The downgrade drops the new tables and columns.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None

STATUSES = "'Pending', 'Documents requested', 'Approved', 'Rejected', 'Withdrawn'"


def upgrade():
    with op.batch_alter_table('credit_applications', schema=None) as batch_op:
        batch_op.add_column(sa.Column('status', sa.String(length=25), server_default='Pending', nullable=False))
        batch_op.add_column(sa.Column('outcome', sa.String(length=10), nullable=True))
        batch_op.add_column(sa.Column('outcome_at', sa.DateTime(), nullable=True))
        batch_op.create_check_constraint('ck_credit_applications_status', f"status IN ({STATUSES})")
        batch_op.create_check_constraint(
            'ck_credit_applications_outcome', "outcome IS NULL OR outcome IN ('Repaid', 'Defaulted')"
        )

    op.create_table(
        'reviews',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('application_id', sa.Integer(), nullable=False),
        sa.Column('analyst_id', sa.Integer(), nullable=False),
        sa.Column('decision', sa.String(length=25), nullable=False),
        sa.Column('justification', sa.Text(), nullable=False),
        sa.Column('followed_model', sa.Boolean(), nullable=True),
        sa.Column('mandatory', sa.Boolean(), nullable=False),
        sa.Column('decided_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint("decision IN ('Approved', 'Rejected', 'Documents requested')", name='ck_reviews_decision'),
        sa.ForeignKeyConstraint(['analyst_id'], ['users.id']),
        sa.ForeignKeyConstraint(['application_id'], ['credit_applications.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('reviews', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_reviews_application_id'), ['application_id'], unique=False)

    op.create_table(
        'inference_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('model', sa.String(length=30), nullable=False),
        sa.Column('model_version', sa.String(length=30), nullable=True),
        sa.Column('result', sa.String(length=20), nullable=True),
        sa.Column('risk_percent', sa.Float(), nullable=True),
        sa.Column('response_ms', sa.Float(), nullable=False),
        sa.Column('error', sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('inference_logs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_inference_logs_created_at'), ['created_at'], unique=False)


def downgrade():
    with op.batch_alter_table('inference_logs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_inference_logs_created_at'))
    op.drop_table('inference_logs')
    with op.batch_alter_table('reviews', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_reviews_application_id'))
    op.drop_table('reviews')
    with op.batch_alter_table('credit_applications', schema=None) as batch_op:
        batch_op.drop_constraint('ck_credit_applications_outcome', type_='check')
        batch_op.drop_constraint('ck_credit_applications_status', type_='check')
        batch_op.drop_column('outcome_at')
        batch_op.drop_column('outcome')
        batch_op.drop_column('status')
