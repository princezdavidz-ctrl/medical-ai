"""Create compliance policies, security incidents and risk register."""
from alembic import op
import sqlalchemy as sa

revision = "0049_compliance_security"
down_revision = "0048_safety_rounds_indicators"
branch_labels = None
depends_on = None

TABLES = ("compliance_policies", "policy_acknowledgements", "security_incidents", "security_incident_events", "compliance_risks")


def upgrade() -> None:
    op.create_table(
        "compliance_policies",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("policy_code", sa.String(80), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("document_reference", sa.String(80), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("effective_at", sa.DateTime(timezone=True)),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("published_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("hospital_id", "policy_code", "version", name="uq_compliance_policy_version"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_compliance_policy_hospital_id"),
        sa.CheckConstraint("status IN ('draft', 'published', 'retired')", name="ck_compliance_policy_status"),
        sa.CheckConstraint("version >= 1", name="ck_compliance_policy_version"),
        sa.CheckConstraint("length(trim(policy_code)) BETWEEN 2 AND 80", name="ck_compliance_policy_code"),
        sa.CheckConstraint("length(trim(title)) BETWEEN 3 AND 180", name="ck_compliance_policy_title"),
        sa.CheckConstraint("document_reference ~ '^vault://[0-9a-fA-F-]{36}$'", name="ck_compliance_policy_document_ref"),
        sa.CheckConstraint("(status = 'published' AND published_by_user_id IS NOT NULL AND published_at IS NOT NULL AND effective_at IS NOT NULL) OR (status != 'published' AND published_by_user_id IS NULL AND published_at IS NULL)", name="ck_compliance_policy_publish_state"),
    )
    op.create_index("ix_compliance_policy_status", "compliance_policies", ["hospital_id", "status", "policy_code"])

    op.create_table(
        "policy_acknowledgements",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("policy_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("acknowledgement_method", sa.String(16), nullable=False, server_default="electronic"),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "policy_id"], ["compliance_policies.hospital_id", "compliance_policies.id"], name="fk_policy_acknowledgement_policy"),
        sa.ForeignKeyConstraint(["hospital_id", "user_id"], ["hospital_memberships.hospital_id", "hospital_memberships.user_id"], name="fk_policy_acknowledgement_member"),
        sa.UniqueConstraint("hospital_id", "policy_id", "user_id", name="uq_policy_acknowledgement_user"),
        sa.CheckConstraint("acknowledgement_method IN ('electronic', 'written', 'in_person')", name="ck_policy_acknowledgement_method"),
    )
    op.create_index("ix_policy_acknowledgement_user", "policy_acknowledgements", ["hospital_id", "user_id", "acknowledged_at"])

    op.create_table(
        "security_incidents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("reporter_user_id", sa.Uuid(), nullable=False),
        sa.Column("reporter_confidential", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("assigned_to_user_id", sa.Uuid()),
        sa.Column("category", sa.String(24), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False, server_default="unclassified"),
        sa.Column("status", sa.String(20), nullable=False, server_default="reported"),
        sa.Column("breach_assessment", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("affected_system", sa.String(180)),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("immediate_actions", sa.Text()),
        sa.Column("reported_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("contained_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "reporter_user_id"], ["hospital_memberships.hospital_id", "hospital_memberships.user_id"], name="fk_security_incident_reporter"),
        sa.ForeignKeyConstraint(["hospital_id", "assigned_to_user_id"], ["hospital_memberships.hospital_id", "hospital_memberships.user_id"], name="fk_security_incident_assignee"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_security_incident_hospital_id"),
        sa.CheckConstraint("category IN ('data_breach', 'unauthorized_access', 'malware', 'loss_or_theft', 'service_disruption', 'insider_threat', 'phishing', 'other')", name="ck_security_incident_category"),
        sa.CheckConstraint("severity IN ('low', 'moderate', 'high', 'critical', 'unclassified')", name="ck_security_incident_severity"),
        sa.CheckConstraint("status IN ('reported', 'triaged', 'investigating', 'contained', 'resolved', 'closed')", name="ck_security_incident_status"),
        sa.CheckConstraint("breach_assessment IN ('pending', 'confirmed', 'not_confirmed', 'not_required')", name="ck_security_incident_breach_assessment"),
        sa.CheckConstraint("length(trim(summary)) BETWEEN 10 AND 5000", name="ck_security_incident_summary"),
    )
    op.create_index("ix_security_incident_queue", "security_incidents", ["hospital_id", "status", "severity", "reported_at"])
    op.create_index("ix_security_incident_assignee", "security_incidents", ["hospital_id", "assigned_to_user_id", "status"])

    op.create_table(
        "security_incident_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("event_metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "incident_id"], ["security_incidents.hospital_id", "security_incidents.id"], name="fk_security_incident_event_incident"),
        sa.CheckConstraint("event_type IN ('reported', 'triaged', 'assigned', 'investigation_started', 'contained', 'breach_assessed', 'resolved', 'closed')", name="ck_security_incident_event_type"),
    )
    op.create_index("ix_security_incident_event_history", "security_incident_events", ["hospital_id", "incident_id", "created_at"])

    op.create_table(
        "compliance_risks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("category", sa.String(24), nullable=False),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("likelihood", sa.Integer(), nullable=False),
        sa.Column("impact", sa.Integer(), nullable=False),
        sa.Column("inherent_score", sa.Integer(), nullable=False),
        sa.Column("residual_likelihood", sa.Integer(), nullable=False),
        sa.Column("residual_impact", sa.Integer(), nullable=False),
        sa.Column("residual_score", sa.Integer(), nullable=False),
        sa.Column("mitigation_plan", sa.Text(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reviewed_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "owner_user_id"], ["hospital_memberships.hospital_id", "hospital_memberships.user_id"], name="fk_compliance_risk_owner"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_compliance_risk_hospital_id"),
        sa.CheckConstraint("category IN ('clinical', 'privacy', 'cybersecurity', 'operational', 'financial', 'regulatory', 'third_party', 'other')", name="ck_compliance_risk_category"),
        sa.CheckConstraint("status IN ('open', 'mitigating', 'accepted', 'closed')", name="ck_compliance_risk_status"),
        sa.CheckConstraint("likelihood BETWEEN 1 AND 5 AND impact BETWEEN 1 AND 5", name="ck_compliance_risk_inherent"),
        sa.CheckConstraint("residual_likelihood BETWEEN 1 AND 5 AND residual_impact BETWEEN 1 AND 5", name="ck_compliance_risk_residual"),
        sa.CheckConstraint("inherent_score = likelihood * impact AND residual_score = residual_likelihood * residual_impact", name="ck_compliance_risk_scores"),
    )
    op.create_index("ix_compliance_risk_status_score", "compliance_risks", ["hospital_id", "status", "inherent_score"])
    op.create_index("ix_compliance_risk_owner_due", "compliance_risks", ["hospital_id", "owner_user_id", "due_at"])

    for table in TABLES:
        op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'CREATE POLICY "{table}_hospital_isolation" ON "{table}" USING (hospital_id = NULLIF(current_setting(\'app.current_hospital_id\', true), \'\')::uuid) WITH CHECK (hospital_id = NULLIF(current_setting(\'app.current_hospital_id\', true), \'\')::uuid)'))

    op.execute("""
        CREATE FUNCTION prevent_security_incident_event_mutation() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'security incident events are append-only';
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("CREATE TRIGGER trg_security_incident_events_immutable BEFORE UPDATE OR DELETE ON security_incident_events FOR EACH ROW EXECUTE FUNCTION prevent_security_incident_event_mutation()")
    op.execute("""
        CREATE FUNCTION prevent_published_compliance_policy_mutation() RETURNS trigger AS $$
        BEGIN
            IF OLD.status = 'published' THEN
                RAISE EXCEPTION 'published compliance policies are immutable; create a new version';
            END IF;
            IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("CREATE TRIGGER trg_compliance_policy_versioned BEFORE UPDATE OR DELETE ON compliance_policies FOR EACH ROW EXECUTE FUNCTION prevent_published_compliance_policy_mutation()")
    op.execute("""
        CREATE FUNCTION prevent_policy_acknowledgement_mutation() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'policy acknowledgements are append-only';
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("CREATE TRIGGER trg_policy_acknowledgements_immutable BEFORE UPDATE OR DELETE ON policy_acknowledgements FOR EACH ROW EXECUTE FUNCTION prevent_policy_acknowledgement_mutation()")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_policy_acknowledgements_immutable ON policy_acknowledgements")
    op.execute("DROP FUNCTION IF EXISTS prevent_policy_acknowledgement_mutation()")
    op.execute("DROP TRIGGER IF EXISTS trg_compliance_policy_versioned ON compliance_policies")
    op.execute("DROP FUNCTION IF EXISTS prevent_published_compliance_policy_mutation()")
    op.execute("DROP TRIGGER IF EXISTS trg_security_incident_events_immutable ON security_incident_events")
    op.execute("DROP FUNCTION IF EXISTS prevent_security_incident_event_mutation()")
    for table in reversed(TABLES):
        op.execute(sa.text(f'DROP POLICY IF EXISTS "{table}_hospital_isolation" ON "{table}"'))
        op.execute(sa.text(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY'))
        op.drop_table(table)
