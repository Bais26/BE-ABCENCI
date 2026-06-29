"""add divisions table

Revision ID: 95699de21c1b
Revises: 5c53c0a88455
Create Date: 2026-04-06 18:02:06.913799

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '95699de21c1b'
down_revision: Union[str, Sequence[str], None] = '5c53c0a88455'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'divisions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # tambah kolom ke karyawan_details
    op.add_column(
        'karyawan_details',
        sa.Column('division_id', sa.UUID(), nullable=True)
    )

    op.create_foreign_key(
        'fk_karyawan_division',
        'karyawan_details',
        'divisions',
        ['division_id'],
        ['id']
    )


def downgrade() -> None:
    op.drop_constraint('fk_karyawan_division', 'karyawan_details', type_='foreignkey')
    op.drop_column('karyawan_details', 'division_id')
    op.drop_table('divisions')
