"""add inbox recipient ownership

Revision ID: b6f41a2c9d10
Revises: a87abef7b17e
Create Date: 2026-07-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b6f41a2c9d10"
down_revision: Union[str, None] = "a87abef7b17e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("inbox_messages") as batch_op:
        batch_op.add_column(sa.Column("recipient_id", sa.String(), nullable=True))
        batch_op.create_foreign_key("fk_inbox_messages_recipient_id_users", "users", ["recipient_id"], ["id"])
        batch_op.create_index("ix_inbox_messages_recipient_id", ["recipient_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("inbox_messages") as batch_op:
        batch_op.drop_index("ix_inbox_messages_recipient_id")
        batch_op.drop_constraint("fk_inbox_messages_recipient_id_users", type_="foreignkey")
        batch_op.drop_column("recipient_id")
