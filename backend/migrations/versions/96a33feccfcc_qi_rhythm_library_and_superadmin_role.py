"""Qi Rhythm Library (platform-wide backing tracks) and the superadmin role

- backing_tracks.organization_id becomes nullable: NULL = Qi Rhythm Library track (owned by
  Eye Forge Studios, available to every organization). Existing tracks keep their organization
  and behave exactly as before (private to that organization).
- One library track per (rhythm, version): partial unique index (the existing unique constraint
  on (organization_id, rhythm_id, version) treats NULLs as distinct).
- instructors.role gains "superadmin" (non-native enum, still VARCHAR(10); no data changes).

Revision ID: 96a33feccfcc
Revises: 3e7b7d953fc2
Create Date: 2026-11-14 12:54:16.202737

"""

import sqlalchemy as sa
from alembic import op

revision = "96a33feccfcc"
down_revision = "3e7b7d953fc2"
branch_labels = None
depends_on = None

OLD_ROLES = sa.Enum("admin", "instructor", name="instructor_role", native_enum=False)
NEW_ROLES = sa.Enum("admin", "instructor", "superadmin", name="instructor_role", native_enum=False)


def upgrade():
    with op.batch_alter_table("instructors") as batch_op:
        batch_op.alter_column("role", existing_type=OLD_ROLES, type_=NEW_ROLES, nullable=False)

    with op.batch_alter_table("backing_tracks") as batch_op:
        batch_op.alter_column("organization_id", existing_type=sa.INTEGER(), nullable=True)
        batch_op.create_index(
            "uq_backing_library_version",
            ["rhythm_id", "version"],
            unique=True,
            postgresql_where=sa.text("organization_id IS NULL"),
        )


def downgrade():
    # The old schema has no library and no superadmin: library tracks (and the measurements made
    # with them) are removed, rounds that used them keep their scores (FK is SET NULL), and
    # super-admins become admins of their own organization. Stored files are left in place.
    op.execute(
        "DELETE FROM music_bleed_profiles WHERE backing_track_id IN "
        "(SELECT id FROM backing_tracks WHERE organization_id IS NULL)"
    )
    op.execute(
        "UPDATE rounds SET backing_track_id = NULL WHERE backing_track_id IN "
        "(SELECT id FROM backing_tracks WHERE organization_id IS NULL)"
    )
    op.execute("DELETE FROM backing_tracks WHERE organization_id IS NULL")
    op.execute("UPDATE instructors SET role = 'admin' WHERE role = 'superadmin'")

    with op.batch_alter_table("backing_tracks") as batch_op:
        batch_op.drop_index(
            "uq_backing_library_version", postgresql_where=sa.text("organization_id IS NULL")
        )
        batch_op.alter_column("organization_id", existing_type=sa.INTEGER(), nullable=False)

    with op.batch_alter_table("instructors") as batch_op:
        batch_op.alter_column("role", existing_type=NEW_ROLES, type_=OLD_ROLES, nullable=False)
