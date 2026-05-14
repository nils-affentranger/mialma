"""remove is_internal from aliases

Revision ID: daf7b009259f
Revises: 03850ca41888
Create Date: 2026-05-14 20:41:32.110254

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'daf7b009259f'
down_revision: Union[str, Sequence[str], None] = '03850ca41888'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('aliases') as batch_op:
        batch_op.drop_column('is_internal')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('aliases', sa.Column('is_internal', sa.BOOLEAN(), nullable=False, server_default=sa.text('0')))
