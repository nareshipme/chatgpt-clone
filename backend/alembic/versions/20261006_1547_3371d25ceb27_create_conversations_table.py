"""create conversations table

Revision ID: 3371d25ceb27
Revises: 7453a75ec4ba
Create Date: 2026-10-06 15:47:29.168064
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '3371d25ceb27'
down_revision: Union[str, None] = '7453a75ec4ba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('conversations',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('archived', sa.Boolean(), server_default=sa.false(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_conversations_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_conversations'))
    )
    op.create_index('ix_conversations_user_id_updated_at', 'conversations', ['user_id', 'updated_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_conversations_user_id_updated_at', table_name='conversations')
    op.drop_table('conversations')
