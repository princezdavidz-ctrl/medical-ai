"""Create ambulance fleet and consent-gated interfacility transport workflows."""
from alembic import op
import sqlalchemy as sa

revision = "0036_ambulance_transport"
down_revision = "0035_facilities"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_patient_consent_hospital_id_patient", "patient_consents",
        ["hospital_id", "id", "patient_id"],
    )
    op.create_table(
        "ambulance_vehicles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("vehicle_code", sa.String(80), nullable=False),
        sa.Column("registration_number", sa.String(40), nullable=False),
        sa.Column("vehicle_type", sa.String(32), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(24), nullable=False, server_default="available"),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("hospital_id", "id", name="uq_ambulance_vehicle_hospital_id"),
        sa.UniqueConstraint("hospital_id", "vehicle_code", name="uq_ambulance_vehicle_code"),
        sa.UniqueConstraint("hospital_id", "registration_number", name="uq_ambulance_vehicle_registration"),
        sa.CheckConstraint("vehicle_type IN ('basic_life_support', 'advanced_life_support', 'patient_transport', 'wheelchair', 'other')", name="ck_ambulance_vehicle_type"),
        sa.CheckConstraint("status IN ('available', 'assigned', 'maintenance', 'out_of_service')", name="ck_ambulance_vehicle_status"),
        sa.CheckConstraint("capacity >= 1 AND capacity <= 20", name="ck_ambulance_vehicle_capacity"),
    )
    op.create_index("ix_ambulance_vehicle_status", "ambulance_vehicles", ["hospital_id", "status", "vehicle_type"])
    op.create_table(
        "transport_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("encounter_id", sa.Uuid(), nullable=False),
        sa.Column("consent_id", sa.Uuid(), nullable=False),
        sa.Column("receiving_hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id")),
        sa.Column("transfer_number", sa.String(80), nullable=False),
        sa.Column("transport_type", sa.String(24), nullable=False),
        sa.Column("priority", sa.String(24), nullable=False, server_default="routine"),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("origin_description", sa.String(500), nullable=False),
        sa.Column("destination_description", sa.String(500), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="requested"),
        sa.Column("requested_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("receiving_accepted_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("receiving_bed_reference", sa.String(120)),
        sa.Column("receiving_accepted_at", sa.DateTime(timezone=True)),
        sa.Column("assigned_vehicle_id", sa.Uuid()),
        sa.Column("assigned_driver_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("assigned_crew_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("dispatched_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("dispatched_at", sa.DateTime(timezone=True)),
        sa.Column("arrived_at", sa.DateTime(timezone=True)),
        sa.Column("arrival_confirmed_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("rejected_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("rejection_reason", sa.String(1000)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_transport_request_patient"),
        sa.ForeignKeyConstraint(["hospital_id", "encounter_id", "patient_id"], ["encounters.hospital_id", "encounters.id", "encounters.patient_id"], name="fk_transport_request_encounter_patient"),
        sa.ForeignKeyConstraint(["hospital_id", "consent_id", "patient_id"], ["patient_consents.hospital_id", "patient_consents.id", "patient_consents.patient_id"], name="fk_transport_request_consent"),
        sa.ForeignKeyConstraint(["hospital_id", "assigned_vehicle_id"], ["ambulance_vehicles.hospital_id", "ambulance_vehicles.id"], name="fk_transport_request_vehicle"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_transport_request_hospital_id"),
        sa.UniqueConstraint("hospital_id", "id", "receiving_hospital_id", name="uq_transport_request_receiver_link"),
        sa.UniqueConstraint("hospital_id", "transfer_number", name="uq_transport_request_number"),
        sa.CheckConstraint("transport_type = 'interfacility'", name="ck_transport_request_type"),
        sa.CheckConstraint("priority IN ('routine', 'urgent', 'emergency')", name="ck_transport_request_priority"),
        sa.CheckConstraint("status IN ('requested', 'accepted', 'bed_accepted', 'vehicle_assigned', 'en_route', 'arrived', 'rejected', 'cancelled')", name="ck_transport_request_status"),
        sa.CheckConstraint("length(trim(origin_description)) >= 3 AND length(trim(destination_description)) >= 3", name="ck_transport_request_locations"),
        sa.CheckConstraint("receiving_hospital_id IS NOT NULL AND receiving_hospital_id != hospital_id", name="ck_transport_interfacility_destination"),
        sa.CheckConstraint("status NOT IN ('bed_accepted', 'vehicle_assigned', 'en_route', 'arrived') OR (receiving_accepted_by_user_id IS NOT NULL AND receiving_bed_reference IS NOT NULL AND receiving_accepted_at IS NOT NULL)", name="ck_transport_bed_acceptance_state"),
        sa.CheckConstraint("status NOT IN ('en_route', 'arrived') OR (dispatched_by_user_id IS NOT NULL AND dispatched_at IS NOT NULL)", name="ck_transport_dispatch_state"),
        sa.CheckConstraint("status != 'arrived' OR (arrived_at IS NOT NULL AND arrival_confirmed_by_user_id IS NOT NULL)", name="ck_transport_arrival_confirmation"),
        sa.CheckConstraint("status != 'rejected' OR (rejected_by_user_id IS NOT NULL AND rejection_reason IS NOT NULL)", name="ck_transport_rejection_state"),
        sa.CheckConstraint("status NOT IN ('vehicle_assigned', 'en_route', 'arrived') OR (assigned_vehicle_id IS NOT NULL AND assigned_driver_user_id IS NOT NULL)", name="ck_transport_vehicle_assignment_state"),
    )
    op.create_index("ix_transport_request_queue", "transport_requests", ["hospital_id", "status", "priority", "created_at"])
    op.create_index("ix_transport_request_destination", "transport_requests", ["receiving_hospital_id", "status", "created_at"])

    op.create_table(
        "transport_receiving_offers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("origin_hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("transport_request_id", sa.Uuid(), nullable=False),
        sa.Column("transfer_number", sa.String(80), nullable=False),
        sa.Column("priority", sa.String(24), nullable=False),
        sa.Column("origin_description", sa.String(500), nullable=False),
        sa.Column("destination_description", sa.String(500), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="offered"),
        sa.Column("bed_reference", sa.String(120)),
        sa.Column("accepted_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.Column("rejected_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("rejection_reason", sa.String(1000)),
        sa.Column("arrival_confirmed_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("arrived_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["origin_hospital_id", "transport_request_id", "hospital_id"], ["transport_requests.hospital_id", "transport_requests.id", "transport_requests.receiving_hospital_id"], name="fk_transport_offer_request_receiver"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_transport_offer_hospital_id"),
        sa.UniqueConstraint("origin_hospital_id", "transport_request_id", name="uq_transport_offer_request"),
        sa.CheckConstraint("status IN ('offered', 'bed_accepted', 'rejected', 'arrived', 'cancelled')", name="ck_transport_offer_status"),
        sa.CheckConstraint("status NOT IN ('bed_accepted', 'arrived') OR (accepted_by_user_id IS NOT NULL AND bed_reference IS NOT NULL AND accepted_at IS NOT NULL)", name="ck_transport_offer_acceptance"),
        sa.CheckConstraint("status != 'rejected' OR (rejected_by_user_id IS NOT NULL AND rejection_reason IS NOT NULL)", name="ck_transport_offer_rejection"),
        sa.CheckConstraint("status != 'arrived' OR (arrival_confirmed_by_user_id IS NOT NULL AND arrived_at IS NOT NULL)", name="ck_transport_offer_arrival"),
    )
    op.create_index("ix_transport_offer_queue", "transport_receiving_offers", ["hospital_id", "status", "created_at"])
    op.create_table(
        "transport_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("transport_request_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("latitude", sa.Float()),
        sa.Column("longitude", sa.Float()),
        sa.Column("note", sa.String(1000)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "transport_request_id"], ["transport_requests.hospital_id", "transport_requests.id"], name="fk_transport_event_request"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_transport_event_hospital_id"),
        sa.CheckConstraint("event_type IN ('requested', 'accepted', 'bed_accepted', 'vehicle_assigned', 'departed', 'location_update', 'arrived', 'rejected', 'cancelled', 'vehicle_released')", name="ck_transport_event_type"),
        sa.CheckConstraint("(latitude IS NULL AND longitude IS NULL) OR (latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180)", name="ck_transport_event_coordinates"),
    )
    op.create_index("ix_transport_event_request_time", "transport_events", ["hospital_id", "transport_request_id", "created_at"])
    op.execute("ALTER TABLE ambulance_vehicles ENABLE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY ambulance_vehicles_hospital_isolation ON ambulance_vehicles USING (hospital_id = NULLIF(current_setting('app.current_hospital_id', true), '')::uuid) WITH CHECK (hospital_id = NULLIF(current_setting('app.current_hospital_id', true), '')::uuid)")
    op.execute("ALTER TABLE transport_requests ENABLE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY transport_requests_origin_isolation ON transport_requests USING (hospital_id = NULLIF(current_setting('app.current_hospital_id', true), '')::uuid) WITH CHECK (hospital_id = NULLIF(current_setting('app.current_hospital_id', true), '')::uuid)")
    op.execute("ALTER TABLE transport_receiving_offers ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY transport_receiving_offers_participant_isolation ON transport_receiving_offers
        USING (
            hospital_id = NULLIF(current_setting('app.current_hospital_id', true), '')::uuid
            OR origin_hospital_id = NULLIF(current_setting('app.current_hospital_id', true), '')::uuid
        )
        WITH CHECK (
            hospital_id = NULLIF(current_setting('app.current_hospital_id', true), '')::uuid
            OR origin_hospital_id = NULLIF(current_setting('app.current_hospital_id', true), '')::uuid
        )
    """)
    op.execute("ALTER TABLE transport_events ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY transport_events_participant_isolation ON transport_events
        USING (
            hospital_id = NULLIF(current_setting('app.current_hospital_id', true), '')::uuid
            OR EXISTS (
                SELECT 1 FROM transport_receiving_offers o
                WHERE o.origin_hospital_id = transport_events.hospital_id
                  AND o.transport_request_id = transport_events.transport_request_id
                  AND o.hospital_id = NULLIF(current_setting('app.current_hospital_id', true), '')::uuid
            )
        )
        WITH CHECK (
            hospital_id = NULLIF(current_setting('app.current_hospital_id', true), '')::uuid
            OR EXISTS (
                SELECT 1 FROM transport_receiving_offers o
                WHERE o.origin_hospital_id = transport_events.hospital_id
                  AND o.transport_request_id = transport_events.transport_request_id
                  AND o.hospital_id = NULLIF(current_setting('app.current_hospital_id', true), '')::uuid
            )
        )
    """)
    op.execute("""
        CREATE FUNCTION prevent_transport_event_mutation() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'transport events are append-only'; END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER trg_transport_events_immutable
        BEFORE UPDATE OR DELETE ON transport_events
        FOR EACH ROW EXECUTE FUNCTION prevent_transport_event_mutation()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_transport_events_immutable ON transport_events")
    op.execute("DROP FUNCTION IF EXISTS prevent_transport_event_mutation()")
    op.execute("DROP POLICY IF EXISTS transport_events_participant_isolation ON transport_events")
    op.execute("ALTER TABLE transport_events DISABLE ROW LEVEL SECURITY")
    op.drop_table("transport_events")
    op.execute("DROP POLICY IF EXISTS transport_receiving_offers_participant_isolation ON transport_receiving_offers")
    op.execute("ALTER TABLE transport_receiving_offers DISABLE ROW LEVEL SECURITY")
    op.drop_table("transport_receiving_offers")
    op.execute("DROP POLICY IF EXISTS transport_requests_origin_isolation ON transport_requests")
    op.execute("ALTER TABLE transport_requests DISABLE ROW LEVEL SECURITY")
    op.drop_table("transport_requests")
    op.execute("DROP POLICY IF EXISTS ambulance_vehicles_hospital_isolation ON ambulance_vehicles")
    op.execute("ALTER TABLE ambulance_vehicles DISABLE ROW LEVEL SECURITY")
    op.drop_table("ambulance_vehicles")
    op.drop_constraint("uq_patient_consent_hospital_id_patient", "patient_consents", type_="unique")
