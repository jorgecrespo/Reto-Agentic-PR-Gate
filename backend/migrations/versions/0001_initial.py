"""Create analysis persistence schema."""

import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pull_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner", sa.String(100), nullable=False),
        sa.Column("repository", sa.String(100), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("url", sa.String(2048), nullable=False, unique=True),
        sa.Column("title", sa.Text()),
        sa.Column("author", sa.String(100)),
    )
    op.create_table(
        "pr_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "pull_request_id", sa.String(36), sa.ForeignKey("pull_requests.id"), nullable=False
        ),
        sa.Column("base_sha", sa.String(64), nullable=False),
        sa.Column("head_sha", sa.String(64), nullable=False),
        sa.Column("draft", sa.Boolean(), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_pr_snapshots_pull_request_id", "pr_snapshots", ["pull_request_id"])
    op.create_index("ix_pr_snapshots_head_sha", "pr_snapshots", ["head_sha"])
    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("snapshot_id", sa.String(36), sa.ForeignKey("pr_snapshots.id")),
        sa.Column("pull_request_url", sa.String(2048), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("model_profile_id", sa.String(100), nullable=False),
        sa.Column("validation_profile_id", sa.String(100), nullable=False),
        sa.Column("policy_version", sa.String(32), nullable=False),
        sa.Column("prompt_version", sa.String(32), nullable=False),
        sa.Column("head_sha", sa.String(64)),
        sa.Column("report_json", sa.Text(), nullable=False),
        sa.Column("error_message", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("input_tokens", sa.Integer()),
        sa.Column("output_tokens", sa.Integer()),
        sa.Column("estimated_cost", sa.Float()),
    )
    op.create_index("ix_analysis_runs_snapshot_id", "analysis_runs", ["snapshot_id"])
    op.create_index("ix_analysis_runs_pull_request_url", "analysis_runs", ["pull_request_url"])
    op.create_index("ix_analysis_runs_status", "analysis_runs", ["status"])
    op.create_table(
        "findings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "analysis_run_id", sa.String(36), sa.ForeignKey("analysis_runs.id"), nullable=False
        ),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("severity", sa.String(32), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("start_line", sa.Integer(), nullable=False),
        sa.Column("end_line", sa.Integer(), nullable=False),
        sa.Column("evidence_excerpt", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("impact", sa.Text(), nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
    )
    op.create_index("ix_findings_analysis_run_id", "findings", ["analysis_run_id"])
    op.create_table(
        "candidate_fixes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("finding_id", sa.String(36), sa.ForeignKey("findings.id"), nullable=False),
        sa.Column("patch", sa.Text(), nullable=False),
        sa.Column("regression_test_patch", sa.Text(), nullable=False),
        sa.Column("patch_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
    )
    op.create_index("ix_candidate_fixes_finding_id", "candidate_fixes", ["finding_id"])
    op.create_table(
        "validation_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "analysis_run_id", sa.String(36), sa.ForeignKey("analysis_runs.id"), nullable=False
        ),
        sa.Column("phase", sa.String(64), nullable=False),
        sa.Column("command_name", sa.String(100), nullable=False),
        sa.Column("exit_code", sa.Integer()),
        sa.Column("stdout_excerpt", sa.Text(), nullable=False),
        sa.Column("stderr_excerpt", sa.Text(), nullable=False),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("timed_out", sa.Boolean(), nullable=False),
        sa.Column("infrastructure_error", sa.Boolean(), nullable=False),
        sa.Column("result", sa.String(32)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_validation_runs_analysis_run_id", "validation_runs", ["analysis_run_id"])
    op.create_table(
        "acceptance_evaluations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "analysis_run_id", sa.String(36), sa.ForeignKey("analysis_runs.id"), nullable=False
        ),
        sa.Column("criterion_id", sa.String(100), nullable=False),
        sa.Column("criterion_text", sa.Text(), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("evidence_json", sa.Text(), nullable=False),
    )
    op.create_index(
        "ix_acceptance_evaluations_analysis_run_id", "acceptance_evaluations", ["analysis_run_id"]
    )


def downgrade() -> None:
    op.drop_table("acceptance_evaluations")
    op.drop_table("validation_runs")
    op.drop_table("candidate_fixes")
    op.drop_table("findings")
    op.drop_table("analysis_runs")
    op.drop_table("pr_snapshots")
    op.drop_table("pull_requests")
