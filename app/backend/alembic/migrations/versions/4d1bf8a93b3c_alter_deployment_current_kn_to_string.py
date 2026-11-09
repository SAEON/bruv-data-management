"""alter_deployment_current_kn_to_string

Revision ID: 4d1bf8a93b3c
Revises: d94cea01d7f2
Create Date: 2026-10-30 15:08:54.127394

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4d1bf8a93b3c'
down_revision: Union[str, Sequence[str], None] = 'd94cea01d7f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        'deployments',
        'current_kn',
        existing_type=sa.Integer(),
        type_=sa.String(),
        existing_nullable=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        'deployments',
        'current_kn',
        existing_type=sa.String(),
        type_=sa.Integer(),
        existing_nullable=True,
    )
