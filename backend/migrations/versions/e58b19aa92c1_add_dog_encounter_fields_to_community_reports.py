"""add dog encounter fields to community reports

Revision ID: e58b19aa92c1
Revises: de47e3e082dd
Create Date: 2026-11-01 11:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e58b19aa92c1'
down_revision: Union[str, None] = 'de47e3e082dd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('community_reports', schema=None) as batch_op:
        batch_op.add_column(sa.Column('encounter_time', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('dog_count', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('is_aggressive', sa.Boolean(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('community_reports', schema=None) as batch_op:
        batch_op.drop_column('is_aggressive')
        batch_op.drop_column('dog_count')
        batch_op.drop_column('encounter_time')
