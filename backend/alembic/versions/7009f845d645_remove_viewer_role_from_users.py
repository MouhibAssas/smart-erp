"""remove viewer role from users

Revision ID: 7009f845d645
Revises: 20260510_remove_viewer_role
Create Date: 2026-05-10 22:13:14.700752

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7009f845d645'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    op.execute("UPDATE users SET role = 'operator' WHERE role = 'viewer'")

    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE userrole RENAME TO userrole_old")
        sa.Enum("admin", "operator", name="userrole").create(bind, checkfirst=False)
        op.execute("ALTER TABLE users ALTER COLUMN role TYPE userrole USING role::text::userrole")
        op.execute("DROP TYPE userrole_old")


def downgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE userrole RENAME TO userrole_new")
        sa.Enum("admin", "operator", "viewer", name="userrole").create(bind, checkfirst=False)
        op.execute("ALTER TABLE users ALTER COLUMN role TYPE userrole USING role::text::userrole")
        op.execute("DROP TYPE userrole_new")
