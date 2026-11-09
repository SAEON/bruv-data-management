"""Add the complete relational field-work schema.

Revision ID: b7d9a3e124af
Revises: 72e95510c527
"""

from alembic import op
import sqlalchemy as sa

from db import models

revision = "b7d9a3e124af"
down_revision = "72e95510c527"
branch_labels = None
depends_on = None

NEW_TABLES = (
    models.UserRole, models.Person, models.Project, models.FieldTrip,
    models.DaySheet, models.Calibration, models.Deployment,
    models.Measurement, models.AnalysisPeriod,
)

OBSERVATION_COLUMNS = (
    "deployment_id", "filename", "frame", "time_mins", "period_number",
    "period_time_mins", "observer_count", "family", "genus", "species",
    "scientific_name", "accepted_name", "opcode_period_species", "abundance",
    "no_lengths", "abundance_type", "has_fed", "emobs_data_type",
)


def _copy_column(column):
    return sa.Column(
        column.name, column.type, nullable=column.nullable,
        server_default=column.server_default,
    )


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "full_name" not in {c["name"] for c in inspector.get_columns("users")}:
        op.add_column("users", sa.Column("full_name", sa.Text(), nullable=True))
    if "description" not in {c["name"] for c in inspector.get_columns("roles")}:
        op.add_column("roles", sa.Column("description", sa.Text(), nullable=True))

    existing_tables = set(inspector.get_table_names())
    for model in NEW_TABLES:
        if model.__table__.name not in existing_tables:
            model.__table__.create(bind=bind)

    existing_observation_columns = {c["name"] for c in inspector.get_columns("observations")}
    for name in OBSERVATION_COLUMNS:
        if name not in existing_observation_columns:
            op.add_column("observations", _copy_column(models.Observation.__table__.c[name]))
    foreign_keys = {fk.get("name") for fk in sa.inspect(bind).get_foreign_keys("observations")}
    if "fk_observations_deployment_id" not in foreign_keys:
        op.create_foreign_key(
            "fk_observations_deployment_id", "observations", "deployments",
            ["deployment_id"], ["id"],
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    foreign_keys = {fk.get("name") for fk in inspector.get_foreign_keys("observations")}
    if "fk_observations_deployment_id" in foreign_keys:
        op.drop_constraint("fk_observations_deployment_id", "observations", type_="foreignkey")
    existing_tables = set(inspector.get_table_names())
    for model in reversed(NEW_TABLES):
        if model.__table__.name in existing_tables:
            model.__table__.drop(bind=bind)

    observation_columns = {c["name"] for c in sa.inspect(bind).get_columns("observations")}
    for name in reversed(OBSERVATION_COLUMNS):
        if name in observation_columns:
            op.drop_column("observations", name)
    if "description" in {c["name"] for c in sa.inspect(bind).get_columns("roles")}:
        op.drop_column("roles", "description")
    if "full_name" in {c["name"] for c in sa.inspect(bind).get_columns("users")}:
        op.drop_column("users", "full_name")
