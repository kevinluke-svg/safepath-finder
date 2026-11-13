"""open data registry and provenance

Revision ID: b2c3d4e5f6a1
Revises: a1b2c3d4e5f6
Create Date: 2026-11-12 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a1'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    # 1. Update evidence_sources with open data provenance fields
    if 'evidence_sources' in tables:
        src_cols = [c['name'] for c in inspector.get_columns('evidence_sources')]
        with op.batch_alter_table('evidence_sources', schema=None) as batch_op:
            if 'source_organisation' not in src_cols:
                batch_op.add_column(sa.Column('source_organisation', sa.String(length=255), server_default='', nullable=False))
            if 'url' not in src_cols:
                batch_op.add_column(sa.Column('url', sa.String(length=500), server_default='', nullable=False))
            if 'licence' not in src_cols:
                batch_op.add_column(sa.Column('licence', sa.String(length=255), server_default='Open Database License (ODbL) 1.0', nullable=False))
            if 'collection_period' not in src_cols:
                batch_op.add_column(sa.Column('collection_period', sa.String(length=100), server_default='', nullable=False))
            if 'last_updated' not in src_cols:
                batch_op.add_column(sa.Column('last_updated', sa.DateTime(timezone=True), nullable=True))
            if 'attribute_definitions' not in src_cols:
                batch_op.add_column(sa.Column('attribute_definitions', sa.JSON(), server_default='{}', nullable=False))
            if 'limitations' not in src_cols:
                batch_op.add_column(sa.Column('limitations', sa.JSON(), server_default='[]', nullable=False))

    # 2. Create dataset_import_history table
    if 'dataset_import_history' not in tables:
        op.create_table(
            'dataset_import_history',
            sa.Column('id', sa.String(length=64), primary_key=True),
            sa.Column('source_id', sa.String(length=64), sa.ForeignKey('evidence_sources.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('import_timestamp', sa.DateTime(timezone=True), nullable=False),
            sa.Column('records_imported', sa.Integer(), server_default='0', nullable=False),
            sa.Column('status', sa.String(length=30), server_default='success', nullable=False),
            sa.Column('file_hash', sa.String(length=64), nullable=True),
            sa.Column('notes', sa.Text(), server_default='', nullable=False)
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if 'dataset_import_history' in tables:
        op.drop_table('dataset_import_history')

    if 'evidence_sources' in tables:
        with op.batch_alter_table('evidence_sources', schema=None) as batch_op:
            batch_op.drop_column('limitations')
            batch_op.drop_column('attribute_definitions')
            batch_op.drop_column('last_updated')
            batch_op.drop_column('collection_period')
            batch_op.drop_column('licence')
            batch_op.drop_column('url')
            batch_op.drop_column('source_organisation')
