"""proposed actions and audit events

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-10-07 11:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql')


def upgrade() -> None:
    op.create_table('proposed_actions',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('tenant_id', sa.String(length=40), nullable=False),
    sa.Column('message_id', sa.Uuid(), nullable=False),
    sa.Column('proposed_by', sa.Uuid(), nullable=False),
    sa.Column('type', sa.String(length=30), nullable=False),
    sa.Column('summary', sa.String(length=300), nullable=False),
    sa.Column('payload', JSON, nullable=False),
    sa.Column('status', sa.String(length=12), server_default='proposed', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('decided_by', sa.Uuid(), nullable=True),
    sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('result', JSON, nullable=True),
    sa.CheckConstraint("status IN ('proposed', 'approved', 'dismissed', 'expired')", name=op.f('ck_proposed_actions_status_valid')),
    sa.ForeignKeyConstraint(['decided_by'], ['users.id'], name=op.f('fk_proposed_actions_decided_by_users'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['message_id'], ['messages.id'], name=op.f('fk_proposed_actions_message_id_messages'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['proposed_by'], ['users.id'], name=op.f('fk_proposed_actions_proposed_by_users'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f('fk_proposed_actions_tenant_id_tenants')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_proposed_actions'))
    )
    op.create_index('ix_proposed_actions_tenant_id_created_at', 'proposed_actions', ['tenant_id', 'created_at'], unique=False)
    op.create_table('audit_events',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('tenant_id', sa.String(length=40), nullable=False),
    sa.Column('actor_id', sa.Uuid(), nullable=True),
    sa.Column('action', sa.String(length=40), nullable=False),
    sa.Column('payload', JSON, nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['actor_id'], ['users.id'], name=op.f('fk_audit_events_actor_id_users'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f('fk_audit_events_tenant_id_tenants')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_audit_events'))
    )
    op.create_index('ix_audit_events_tenant_id_created_at', 'audit_events', ['tenant_id', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_audit_events_tenant_id_created_at', table_name='audit_events')
    op.drop_table('audit_events')
    op.drop_index('ix_proposed_actions_tenant_id_created_at', table_name='proposed_actions')
    op.drop_table('proposed_actions')
