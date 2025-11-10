"""Corrige typo em provisão extras

Revision ID: 7b28be5558f8
Revises: 978ad2794883
Create Date: 2025-11-10 00:01:25.372130

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7b28be5558f8'
down_revision = '978ad2794883'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('configuracao') as batch_op:
        batch_op.alter_column('provicao_extras', new_column_name='provisao_extras')



def downgrade():
    with op.batch_alter_table('configuracao') as batch_op:
        batch_op.alter_column('provisao_extras', new_column_name='provicao_extras')

