"""phase1 infrastructure and corroborations

Revision ID: f1a2b3c4d5e6
Revises: e58b19aa92c1
Create Date: 2026-11-01 12:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = 'e58b19aa92c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    # 1. Update community_reports
    comm_cols = [c['name'] for c in inspector.get_columns('community_reports')]
    with op.batch_alter_table('community_reports', schema=None) as batch_op:
        if 'location_confidence' not in comm_cols:
            batch_op.add_column(sa.Column('location_confidence', sa.String(length=30), server_default='user_pinned', nullable=False))
        if 'duplicate_of_id' not in comm_cols:
            batch_op.add_column(sa.Column('duplicate_of_id', sa.String(length=36), nullable=True))

    # 2. Update street_segments
    seg_cols = [c['name'] for c in inspector.get_columns('street_segments')]
    with op.batch_alter_table('street_segments', schema=None) as batch_op:
        if 'sidewalk_status' not in seg_cols:
            batch_op.add_column(sa.Column('sidewalk_status', sa.String(length=30), server_default='unmapped', nullable=False))
        if 'crossing_status' not in seg_cols:
            batch_op.add_column(sa.Column('crossing_status', sa.String(length=30), server_default='unmapped', nullable=False))
        if 'has_tactile_paving' not in seg_cols:
            batch_op.add_column(sa.Column('has_tactile_paving', sa.Boolean(), nullable=True))
        if 'crossing_difficulty' not in seg_cols:
            batch_op.add_column(sa.Column('crossing_difficulty', sa.String(length=30), server_default='unknown', nullable=False))
        if 'infrastructure_summary' not in seg_cols:
            batch_op.add_column(sa.Column('infrastructure_summary', sa.JSON(), server_default='{}', nullable=False))

    # 3. Create report_corroborations table if not exists
    tables = inspector.get_table_names()
    if 'report_corroborations' not in tables:
        op.create_table(
            'report_corroborations',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('report_id', sa.String(length=36), nullable=False),
            sa.Column('user_id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(['report_id'], ['community_reports.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_corroboration_report_user', 'report_corroborations', ['report_id', 'user_id'], unique=True)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    
    if 'report_corroborations' in tables:
        op.drop_index('ix_corroboration_report_user', table_name='report_corroborations')
        op.drop_table('report_corroborations')

    with op.batch_alter_table('street_segments', schema=None) as batch_op:
        batch_op.drop_column('infrastructure_summary')
        batch_op.drop_column('crossing_difficulty')
        batch_op.drop_column('has_tactile_paving')
        batch_op.drop_column('crossing_status')
        batch_op.drop_column('sidewalk_status')

    with op.batch_alter_table('community_reports', schema=None) as batch_op:
        batch_op.drop_column('duplicate_of_id')
        batch_op.drop_column('location_confidence')
