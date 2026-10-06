"""tenants, user tenant and role

Revision ID: a1b2c3d4e5f6
Revises: 1fc7175345b5
Create Date: 2026-10-06 18:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '1fc7175345b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TENANTS = [
    ('northwind', 'Northwind Grocers', 'Grocery retail'),
    ('harbor', 'Harbor Freight Lines', 'Regional logistics'),
]


def upgrade() -> None:
    tenants = op.create_table('tenants',
    sa.Column('id', sa.String(length=40), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('industry', sa.String(length=60), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_tenants'))
    )
    op.bulk_insert(tenants, [{'id': i, 'name': n, 'industry': k} for i, n, k in TENANTS])
    # Existing users (created before tenants existed) join the first demo tenant.
    with op.batch_alter_table('users') as batch:
        batch.add_column(sa.Column('tenant_id', sa.String(length=40), server_default='northwind', nullable=False))
        batch.add_column(sa.Column('role', sa.String(length=16), server_default='planner', nullable=False))
        batch.create_foreign_key(op.f('fk_users_tenant_id_tenants'), 'tenants', ['tenant_id'], ['id'])
        batch.create_check_constraint(op.f('ck_users_role_valid'), "role IN ('planner', 'manager', 'viewer')")


def downgrade() -> None:
    with op.batch_alter_table('users') as batch:
        batch.drop_constraint(op.f('ck_users_role_valid'), type_='check')
        batch.drop_constraint(op.f('fk_users_tenant_id_tenants'), type_='foreignkey')
        batch.drop_column('role')
        batch.drop_column('tenant_id')
    op.drop_table('tenants')
