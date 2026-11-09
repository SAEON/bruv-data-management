"""set_boolean_columns_default_to_false

Revision ID: 36c9515b59e3
Revises: 4d1bf8a93b3c
Create Date: 2026-10-30 15:56:36.594407

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '36c9515b59e3'
down_revision: Union[str, Sequence[str], None] = '4d1bf8a93b3c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("UPDATE calibrations SET cal_success = false WHERE cal_success IS NULL")
    op.execute("UPDATE observations SET has_fed = false WHERE has_fed IS NULL")

    op.alter_column(
        'calibrations',
        'cal_success',
        existing_type=sa.Boolean(),
        server_default=sa.text('false'),
        existing_nullable=True,
    )
    op.alter_column(
        'observations',
        'has_fed',
        existing_type=sa.Boolean(),
        server_default=sa.text('false'),
        existing_nullable=True,
    )
    op.alter_column(
        'users',
        'is_active',
        existing_type=sa.Boolean(),
        server_default=sa.text('false'),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        'users',
        'is_active',
        existing_type=sa.Boolean(),
        server_default=None,
        existing_nullable=False,
    )
    op.alter_column(
        'observations',
        'has_fed',
        existing_type=sa.Boolean(),
        server_default=None,
        existing_nullable=True,
    )
    op.alter_column(
        'calibrations',
        'cal_success',
        existing_type=sa.Boolean(),
        server_default=None,
        existing_nullable=True,
    )
