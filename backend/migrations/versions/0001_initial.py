"""Initial analysis and validation tables."""

import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("pull_request_url", sa.String(2048), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("model_profile_id", sa.String(100), nullable=False),
        sa.Column("validation_profile_id", sa.String(100), nullable=False),
        sa.Column("head_sha", sa.String(64)),
        sa.Column("report_json", sa.Text(), nullable=False),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_analysis_runs_pull_request_url", "analysis_runs", ["pull_request_url"])
    op.create_index("ix_analysis_runs_status", "analysis_runs", ["status"])
    op.create_table(
        "validation_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("analysis_run_id", sa.String(36), nullable=False),
        sa.Column("phase", sa.String(64), nullable=False),
        sa.Column("command_name", sa.String(100), nullable=False),
        sa.Column("exit_code", sa.Integer()),
        sa.Column("stdout_excerpt", sa.Text(), nullable=False),
        sa.Column("stderr_excerpt", sa.Text(), nullable=False),
        sa.Column("timed_out", sa.Boolean(), nullable=False),
        sa.Column("infrastructure_error", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_validation_runs_analysis_run_id", "validation_runs", ["analysis_run_id"])


def downgrade() -> None:
    op.drop_table("validation_runs")
    op.drop_table("analysis_runs")
