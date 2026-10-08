"""Persist manual webcam pause commands without finalizing the job."""

import sqlalchemy as sa

from alembic import op

revision = "0012_live_manual_pause"
down_revision = "0011_live_zone_dwell"
branch_labels = None
depends_on = None


def replace_check(table, column, expression):
    for check in sa.inspect(op.get_bind()).get_check_constraints(table):
        if column in check["sqltext"]:
            op.drop_constraint(check["name"], table, type_="check")
    op.create_check_constraint(f"ck_{table}_{column}", table, expression)


def upgrade():
    for column in ("pause_requested_at", "paused_at", "resume_requested_at"):
        op.add_column("live_analysis_states", sa.Column(column, sa.DateTime(timezone=True)))
    replace_check(
        "live_analysis_states",
        "capture_status",
        "capture_status IN ('starting','connected','interrupted',"
        "'awaiting_confirmation','pausing','paused','stopping','ended')",
    )
    replace_check(
        "live_capture_segments",
        "reason",
        "reason IN ('initial','reconnected','analysis_gap','operator_resume')",
    )
    replace_check(
        "live_interruptions",
        "reason",
        "reason IN ('capture_lost','analysis_gap','awaiting_confirmation',"
        "'worker_interrupted','database_unavailable','operator_pause')",
    )


def downgrade():
    active = op.get_bind().scalar(
        sa.text(
            "SELECT count(*) FROM live_analysis_states s JOIN processing_jobs j ON j.id=s.job_id "
            "WHERE j.status IN ('pending','processing') AND "
            "(s.pause_requested_at IS NOT NULL OR s.capture_status IN ('pausing','paused'))"
        )
    )
    if active:
        raise RuntimeError("Stop paused webcam jobs before downgrading")
    op.execute(
        "UPDATE live_capture_segments SET reason='reconnected' WHERE reason='operator_resume'"
    )
    op.execute("UPDATE live_interruptions SET reason='capture_lost' WHERE reason='operator_pause'")
    replace_check(
        "live_capture_segments", "reason", "reason IN ('initial','reconnected','analysis_gap')"
    )
    replace_check(
        "live_interruptions",
        "reason",
        "reason IN ('capture_lost','analysis_gap','awaiting_confirmation',"
        "'worker_interrupted','database_unavailable')",
    )
    replace_check(
        "live_analysis_states",
        "capture_status",
        "capture_status IN ('starting','connected','interrupted',"
        "'awaiting_confirmation','stopping','ended')",
    )
    for column in ("resume_requested_at", "paused_at", "pause_requested_at"):
        op.drop_column("live_analysis_states", column)
