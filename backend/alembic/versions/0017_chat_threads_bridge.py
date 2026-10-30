"""Bridge revision if a prior 0017_chat_threads was stamped before v2.

Keeps local test DBs recoverable when the revision id was renamed.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0017_chat_threads"
down_revision: str | None = "0016_possible_purchase"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Real schema is created in 0017_chat_threads_v2.
    pass


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS chat_messages CASCADE")
    op.execute("DROP TABLE IF EXISTS chat_threads CASCADE")
