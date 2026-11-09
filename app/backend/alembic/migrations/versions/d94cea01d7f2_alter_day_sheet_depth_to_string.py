"""alter_day_sheet_depth_to_string

Revision ID: d94cea01d7f2
Revises: 99dbf7caf206
Create Date: 2026-10-29 15:17:19.554522

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd94cea01d7f2'
down_revision: Union[str, Sequence[str], None] = '99dbf7caf206'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        'day_sheets',
        'depth',
        existing_type=sa.Integer(),
        type_=sa.String(),
        existing_nullable=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        'day_sheets',
        'depth',
        existing_type=sa.String(),
        type_=sa.Integer(),
        existing_nullable=True,
    )
