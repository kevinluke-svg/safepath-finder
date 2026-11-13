"""phase3 journey sessions and report confirmations

Revision ID: a1b2c3d4e5f6
Revises: f1a2b3c4d5e6
Create Date: 2026-11-01 14:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    # 1. Update community_reports with outdated_flags
    if 'community_reports' in tables:
        comm_cols = [c['name'] for c in inspector.get_columns('community_reports')]
        with op.batch_alter_table('community_reports', schema=None) as batch_op:
            if 'outdated_flags' not in comm_cols:
                batch_op.add_column(sa.Column('outdated_flags', sa.Integer(), server_default='0', nullable=False))

    # 2. Update report_corroborations with action column
    if 'report_corroborations' in tables:
        corr_cols = [c['name'] for c in inspector.get_columns('report_corroborations')]
        with op.batch_alter_table('report_corroborations', schema=None) as batch_op:
            if 'action' not in corr_cols:
                batch_op.add_column(sa.Column('action', sa.String(length=30), server_default='confirm_present', nullable=False))

    # 3. Create journey_sessions table
    if 'journey_sessions' not in tables:
        op.create_table(
            'journey_sessions',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('user_id', sa.String(length=36), nullable=False),
            sa.Column('token', sa.String(length=64), nullable=False),
            sa.Column('origin', sa.String(length=255), nullable=False),
            sa.Column('destination', sa.String(length=255), nullable=False),
            sa.Column('route_name', sa.String(length=120), nullable=False),
            sa.Column('route_id', sa.String(length=64), nullable=False),
            sa.Column('eta_minutes', sa.Integer(), nullable=False),
            sa.Column('distance_meters', sa.Integer(), server_default='0', nullable=False),
            sa.Column('status', sa.String(length=30), server_default='active', nullable=False),
            sa.Column('consent_given', sa.Boolean(), server_default='1', nullable=False),
            sa.Column('contact_count', sa.Integer(), server_default='1', nullable=False),
            sa.Column('contact_ids', sa.Text(), server_default='', nullable=False),
            sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('expected_arrival_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('is_revoked', sa.Boolean(), server_default='0', nullable=False),
            sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('reminder_sent', sa.Boolean(), server_default='0', nullable=False),
            sa.Column('overdue_notified', sa.Boolean(), server_default='0', nullable=False),
            sa.Column('notification_mode', sa.String(length=50), server_default='simulated_development', nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_journey_sessions_token', 'journey_sessions', ['token'], unique=True)
        op.create_index('ix_journey_sessions_user_id', 'journey_sessions', ['user_id'], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if 'journey_sessions' in tables:
        op.drop_table('journey_sessions')

    if 'report_corroborations' in tables:
        with op.batch_alter_table('report_corroborations', schema=None) as batch_op:
            batch_op.drop_column('action')

    if 'community_reports' in tables:
        with op.batch_alter_table('community_reports', schema=None) as batch_op:
            batch_op.drop_column('outdated_flags')
