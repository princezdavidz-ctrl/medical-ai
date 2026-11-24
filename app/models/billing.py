import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index,
    Numeric, String, Text, UniqueConstraint, Uuid, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BillingServiceDefinition(Base):
    __tablename__ = "billing_service_definitions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "department_id"],
            ["departments.hospital_id", "departments.id"],
            name="fk_billing_service_department",
        ),
        UniqueConstraint("hospital_id", "id", name="uq_billing_service_hospital_id"),
        UniqueConstraint("hospital_id", "code", name="uq_billing_service_code"),
        CheckConstraint("status IN ('draft', 'active', 'retired')", name="ck_billing_service_status"),
        CheckConstraint(
            "(status = 'draft' AND approved_by_user_id IS NULL AND approved_at IS NULL "
            "AND retired_by_user_id IS NULL AND retired_at IS NULL AND retirement_reason IS NULL) OR "
            "(status = 'active' AND approved_by_user_id IS NOT NULL AND approved_at IS NOT NULL "
            "AND retired_by_user_id IS NULL AND retired_at IS NULL AND retirement_reason IS NULL) OR "
            "(status = 'retired' AND approved_by_user_id IS NOT NULL AND approved_at IS NOT NULL "
            "AND retired_by_user_id IS NOT NULL AND retired_at IS NOT NULL "
            "AND retirement_reason IS NOT NULL AND length(trim(retirement_reason)) >= 3)",
            name="ck_billing_service_approval_state",
        ),
        CheckConstraint(
            "approved_by_user_id IS NULL OR approved_by_user_id != created_by_user_id",
            name="ck_billing_service_two_person",
        ),
        CheckConstraint("unit_price >= 0", name="ck_billing_service_price"),
        CheckConstraint("length(trim(code)) >= 2 AND length(trim(name)) >= 2", name="ck_billing_service_text"),
        CheckConstraint("currency ~ '^[A-Z]{3}", name="ck_billing_service_currency"),
        Index("ix_billing_service_department_status", "hospital_id", "department_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    department_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="KES")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retired_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retirement_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "patient_id"],
            ["patients.hospital_id", "patients.id"],
            name="fk_invoice_patient",
        ),
        ForeignKeyConstraint(
            ["hospital_id", "encounter_id", "patient_id"],
            ["encounters.hospital_id", "encounters.id", "encounters.patient_id"],
            name="fk_invoice_encounter_patient",
        ),
        ForeignKeyConstraint(
            ["hospital_id", "department_id"],
            ["departments.hospital_id", "departments.id"],
            name="fk_invoice_department",
        ),
        UniqueConstraint("hospital_id", "id", name="uq_invoice_hospital_id"),
        UniqueConstraint("hospital_id", "invoice_number", name="uq_invoice_number"),
        CheckConstraint(
            "status IN ('draft', 'issued', 'partially_paid', 'paid', 'void')",
            name="ck_invoice_status",
        ),
        CheckConstraint("length(currency) = 3 AND currency = upper(currency)", name="ck_invoice_currency"),
        CheckConstraint("subtotal_total >= 0 AND amount_paid_total >= 0", name="ck_invoice_amounts_nonnegative"),
        CheckConstraint("amount_paid_total <= subtotal_total", name="ck_invoice_amount_paid_limit"),
        CheckConstraint(
            "(status = 'draft' AND issued_by_user_id IS NULL AND issued_at IS NULL "
            "AND amount_paid_total = 0 AND void_by_user_id IS NULL AND void_at IS NULL AND void_reason IS NULL) OR "
            "(status = 'issued' AND issued_by_user_id IS NOT NULL AND issued_at IS NOT NULL "
            "AND amount_paid_total = 0 AND void_by_user_id IS NULL AND void_at IS NULL AND void_reason IS NULL) OR "
            "(status = 'partially_paid' AND issued_by_user_id IS NOT NULL AND issued_at IS NOT NULL "
            "AND amount_paid_total > 0 AND amount_paid_total < subtotal_total "
            "AND void_by_user_id IS NULL AND void_at IS NULL AND void_reason IS NULL) OR "
            "(status = 'paid' AND issued_by_user_id IS NOT NULL AND issued_at IS NOT NULL "
            "AND amount_paid_total = subtotal_total "
            "AND void_by_user_id IS NULL AND void_at IS NULL AND void_reason IS NULL) OR "
            "(status = 'void' AND void_by_user_id IS NOT NULL AND void_at IS NOT NULL "
            "AND void_reason IS NOT NULL AND length(trim(void_reason)) >= 3 AND amount_paid_total = 0)",
            name="ck_invoice_lifecycle_state",
        ),
        CheckConstraint("length(trim(invoice_number)) >= 3", name="ck_invoice_number_text"),
        Index("ix_invoice_patient_created", "hospital_id", "patient_id", "created_at"),
        Index("ix_invoice_encounter", "hospital_id", "encounter_id"),
        Index("ix_invoice_department_status", "hospital_id", "department_id", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    encounter_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    department_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    invoice_number: Mapped[str] = mapped_column(String(80), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="KES")
    subtotal_total: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False, default=Decimal("0"))
    amount_paid_total: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False, default=Decimal("0"))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    issued_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    void_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    void_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    void_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class InvoiceLine(Base):
    __tablename__ = "invoice_lines"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "invoice_id"],
            ["invoices.hospital_id", "invoices.id"],
            name="fk_invoice_line_invoice",
        ),
        ForeignKeyConstraint(
            ["hospital_id", "service_definition_id"],
            ["billing_service_definitions.hospital_id", "billing_service_definitions.id"],
            name="fk_invoice_line_service",
        ),
        CheckConstraint("quantity > 0", name="ck_invoice_line_quantity"),
        CheckConstraint("unit_price >= 0 AND line_total >= 0", name="ck_invoice_line_amounts"),
        CheckConstraint(
            "line_total = round(quantity * unit_price, 2)",
            name="ck_invoice_line_total_calculation",
        ),
        CheckConstraint("length(trim(description)) >= 2", name="ck_invoice_line_description"),
        CheckConstraint("length(currency) = 3 AND currency = upper(currency)", name="ck_invoice_line_currency"),
        Index("ix_invoice_line_invoice", "hospital_id", "invoice_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    invoice_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    service_definition_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    description: Mapped[str] = mapped_column(String(240), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class InvoicePayment(Base):
    __tablename__ = "invoice_payments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "invoice_id"],
            ["invoices.hospital_id", "invoices.id"],
            name="fk_invoice_payment_invoice",
        ),
        UniqueConstraint("hospital_id", "id", name="uq_invoice_payment_hospital_id"),
        UniqueConstraint("hospital_id", "external_reference", name="uq_invoice_payment_external_reference"),
        CheckConstraint("status IN ('pending', 'confirmed', 'failed')", name="ck_invoice_payment_status"),
        CheckConstraint("amount > 0", name="ck_invoice_payment_amount"),
        CheckConstraint("method IN ('cash', 'card', 'bank_transfer', 'mobile_money', 'cheque', 'other')", name="ck_invoice_payment_method"),
        CheckConstraint("length(currency) = 3 AND currency = upper(currency)", name="ck_invoice_payment_currency"),
        CheckConstraint(
            "(status = 'pending' AND confirmed_by_user_id IS NULL AND confirmed_at IS NULL AND failure_note IS NULL) OR "
            "(status = 'confirmed' AND confirmed_by_user_id IS NOT NULL AND confirmed_at IS NOT NULL "
            "AND confirmed_by_user_id != created_by_user_id AND failure_note IS NULL) OR "
            "(status = 'failed' AND confirmed_by_user_id IS NULL AND confirmed_at IS NULL "
            "AND failure_note IS NOT NULL AND length(trim(failure_note)) >= 3)",
            name="ck_invoice_payment_lifecycle_state",
        ),
        Index("ix_invoice_payment_invoice_time", "hospital_id", "invoice_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    invoice_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    method: Mapped[str] = mapped_column(String(24), nullable=False)
    external_reference: Mapped[str | None] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    confirmed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
", name="ck_billing_service_currency"),
        Index("ix_billing_service_department_status", "hospital_id", "department_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    department_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="KES")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retired_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retirement_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "patient_id"],
            ["patients.hospital_id", "patients.id"],
            name="fk_invoice_patient",
        ),
        ForeignKeyConstraint(
            ["hospital_id", "encounter_id", "patient_id"],
            ["encounters.hospital_id", "encounters.id", "encounters.patient_id"],
            name="fk_invoice_encounter_patient",
        ),
        ForeignKeyConstraint(
            ["hospital_id", "department_id"],
            ["departments.hospital_id", "departments.id"],
            name="fk_invoice_department",
        ),
        UniqueConstraint("hospital_id", "id", name="uq_invoice_hospital_id"),
        UniqueConstraint("hospital_id", "invoice_number", name="uq_invoice_number"),
        CheckConstraint(
            "status IN ('draft', 'issued', 'partially_paid', 'paid', 'void')",
            name="ck_invoice_status",
        ),
        CheckConstraint("currency ~ '^[A-Z]{3}", name="ck_invoice_currency"),
        CheckConstraint("subtotal_total >= 0 AND amount_paid_total >= 0", name="ck_invoice_amounts_nonnegative"),
        CheckConstraint("amount_paid_total <= subtotal_total", name="ck_invoice_amount_paid_limit"),
        CheckConstraint(
            "(status = 'draft' AND issued_by_user_id IS NULL AND issued_at IS NULL "
            "AND amount_paid_total = 0 AND void_by_user_id IS NULL AND void_at IS NULL AND void_reason IS NULL) OR "
            "(status = 'issued' AND issued_by_user_id IS NOT NULL AND issued_at IS NOT NULL "
            "AND amount_paid_total = 0 AND void_by_user_id IS NULL AND void_at IS NULL AND void_reason IS NULL) OR "
            "(status = 'partially_paid' AND issued_by_user_id IS NOT NULL AND issued_at IS NOT NULL "
            "AND amount_paid_total > 0 AND amount_paid_total < subtotal_total "
            "AND void_by_user_id IS NULL AND void_at IS NULL AND void_reason IS NULL) OR "
            "(status = 'paid' AND issued_by_user_id IS NOT NULL AND issued_at IS NOT NULL "
            "AND amount_paid_total = subtotal_total "
            "AND void_by_user_id IS NULL AND void_at IS NULL AND void_reason IS NULL) OR "
            "(status = 'void' AND void_by_user_id IS NOT NULL AND void_at IS NOT NULL "
            "AND void_reason IS NOT NULL AND length(trim(void_reason)) >= 3 AND amount_paid_total = 0)",
            name="ck_invoice_lifecycle_state",
        ),
        CheckConstraint("length(trim(invoice_number)) >= 3", name="ck_invoice_number_text"),
        Index("ix_invoice_patient_created", "hospital_id", "patient_id", "created_at"),
        Index("ix_invoice_encounter", "hospital_id", "encounter_id"),
        Index("ix_invoice_department_status", "hospital_id", "department_id", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    encounter_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    department_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    invoice_number: Mapped[str] = mapped_column(String(80), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="KES")
    subtotal_total: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False, default=Decimal("0"))
    amount_paid_total: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False, default=Decimal("0"))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    issued_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    void_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    void_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    void_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class InvoiceLine(Base):
    __tablename__ = "invoice_lines"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "invoice_id"],
            ["invoices.hospital_id", "invoices.id"],
            name="fk_invoice_line_invoice",
        ),
        ForeignKeyConstraint(
            ["hospital_id", "service_definition_id"],
            ["billing_service_definitions.hospital_id", "billing_service_definitions.id"],
            name="fk_invoice_line_service",
        ),
        CheckConstraint("quantity > 0", name="ck_invoice_line_quantity"),
        CheckConstraint("unit_price >= 0 AND line_total >= 0", name="ck_invoice_line_amounts"),
        CheckConstraint(
            "line_total = round(quantity * unit_price, 2)",
            name="ck_invoice_line_total_calculation",
        ),
        CheckConstraint("length(trim(description)) >= 2", name="ck_invoice_line_description"),
        CheckConstraint("length(currency) = 3 AND currency = upper(currency)", name="ck_invoice_line_currency"),
        Index("ix_invoice_line_invoice", "hospital_id", "invoice_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    invoice_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    service_definition_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    description: Mapped[str] = mapped_column(String(240), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class InvoicePayment(Base):
    __tablename__ = "invoice_payments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "invoice_id"],
            ["invoices.hospital_id", "invoices.id"],
            name="fk_invoice_payment_invoice",
        ),
        UniqueConstraint("hospital_id", "id", name="uq_invoice_payment_hospital_id"),
        UniqueConstraint("hospital_id", "external_reference", name="uq_invoice_payment_external_reference"),
        CheckConstraint("status IN ('pending', 'confirmed', 'failed')", name="ck_invoice_payment_status"),
        CheckConstraint("amount > 0", name="ck_invoice_payment_amount"),
        CheckConstraint("method IN ('cash', 'card', 'bank_transfer', 'mobile_money', 'cheque', 'other')", name="ck_invoice_payment_method"),
        CheckConstraint("length(currency) = 3 AND currency = upper(currency)", name="ck_invoice_payment_currency"),
        CheckConstraint(
            "(status = 'pending' AND confirmed_by_user_id IS NULL AND confirmed_at IS NULL AND failure_note IS NULL) OR "
            "(status = 'confirmed' AND confirmed_by_user_id IS NOT NULL AND confirmed_at IS NOT NULL "
            "AND confirmed_by_user_id != created_by_user_id AND failure_note IS NULL) OR "
            "(status = 'failed' AND confirmed_by_user_id IS NULL AND confirmed_at IS NULL "
            "AND failure_note IS NOT NULL AND length(trim(failure_note)) >= 3)",
            name="ck_invoice_payment_lifecycle_state",
        ),
        Index("ix_invoice_payment_invoice_time", "hospital_id", "invoice_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    invoice_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    method: Mapped[str] = mapped_column(String(24), nullable=False)
    external_reference: Mapped[str | None] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    confirmed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
", name="ck_invoice_currency"),
        CheckConstraint("subtotal_total >= 0 AND amount_paid_total >= 0", name="ck_invoice_amounts_nonnegative"),
        CheckConstraint("amount_paid_total <= subtotal_total", name="ck_invoice_amount_paid_limit"),
        CheckConstraint(
            "(status = 'draft' AND issued_by_user_id IS NULL AND issued_at IS NULL "
            "AND amount_paid_total = 0 AND void_by_user_id IS NULL AND void_at IS NULL AND void_reason IS NULL) OR "
            "(status = 'issued' AND issued_by_user_id IS NOT NULL AND issued_at IS NOT NULL "
            "AND amount_paid_total = 0 AND void_by_user_id IS NULL AND void_at IS NULL AND void_reason IS NULL) OR "
            "(status = 'partially_paid' AND issued_by_user_id IS NOT NULL AND issued_at IS NOT NULL "
            "AND amount_paid_total > 0 AND amount_paid_total < subtotal_total "
            "AND void_by_user_id IS NULL AND void_at IS NULL AND void_reason IS NULL) OR "
            "(status = 'paid' AND issued_by_user_id IS NOT NULL AND issued_at IS NOT NULL "
            "AND amount_paid_total = subtotal_total "
            "AND void_by_user_id IS NULL AND void_at IS NULL AND void_reason IS NULL) OR "
            "(status = 'void' AND void_by_user_id IS NOT NULL AND void_at IS NOT NULL "
            "AND void_reason IS NOT NULL AND length(trim(void_reason)) >= 3 AND amount_paid_total = 0)",
            name="ck_invoice_lifecycle_state",
        ),
        CheckConstraint("length(trim(invoice_number)) >= 3", name="ck_invoice_number_text"),
        Index("ix_invoice_patient_created", "hospital_id", "patient_id", "created_at"),
        Index("ix_invoice_encounter", "hospital_id", "encounter_id"),
        Index("ix_invoice_department_status", "hospital_id", "department_id", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    encounter_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    department_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    invoice_number: Mapped[str] = mapped_column(String(80), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="KES")
    subtotal_total: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False, default=Decimal("0"))
    amount_paid_total: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False, default=Decimal("0"))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    issued_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    void_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    void_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    void_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class InvoiceLine(Base):
    __tablename__ = "invoice_lines"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "invoice_id"],
            ["invoices.hospital_id", "invoices.id"],
            name="fk_invoice_line_invoice",
        ),
        ForeignKeyConstraint(
            ["hospital_id", "service_definition_id"],
            ["billing_service_definitions.hospital_id", "billing_service_definitions.id"],
            name="fk_invoice_line_service",
        ),
        CheckConstraint("quantity > 0", name="ck_invoice_line_quantity"),
        CheckConstraint("unit_price >= 0 AND line_total >= 0", name="ck_invoice_line_amounts"),
        CheckConstraint(
            "line_total = round(quantity * unit_price, 2)",
            name="ck_invoice_line_total_calculation",
        ),
        CheckConstraint("length(trim(description)) >= 2", name="ck_invoice_line_description"),
        CheckConstraint("currency ~ '^[A-Z]{3}", name="ck_invoice_line_currency"),
        Index("ix_invoice_line_invoice", "hospital_id", "invoice_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    invoice_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    service_definition_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    description: Mapped[str] = mapped_column(String(240), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class InvoicePayment(Base):
    __tablename__ = "invoice_payments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "invoice_id"],
            ["invoices.hospital_id", "invoices.id"],
            name="fk_invoice_payment_invoice",
        ),
        UniqueConstraint("hospital_id", "id", name="uq_invoice_payment_hospital_id"),
        UniqueConstraint("hospital_id", "external_reference", name="uq_invoice_payment_external_reference"),
        CheckConstraint("status IN ('pending', 'confirmed', 'failed')", name="ck_invoice_payment_status"),
        CheckConstraint("amount > 0", name="ck_invoice_payment_amount"),
        CheckConstraint("method IN ('cash', 'card', 'bank_transfer', 'mobile_money', 'cheque', 'other')", name="ck_invoice_payment_method"),
        CheckConstraint("length(currency) = 3 AND currency = upper(currency)", name="ck_invoice_payment_currency"),
        CheckConstraint(
            "(status = 'pending' AND confirmed_by_user_id IS NULL AND confirmed_at IS NULL AND failure_note IS NULL) OR "
            "(status = 'confirmed' AND confirmed_by_user_id IS NOT NULL AND confirmed_at IS NOT NULL "
            "AND confirmed_by_user_id != created_by_user_id AND failure_note IS NULL) OR "
            "(status = 'failed' AND confirmed_by_user_id IS NULL AND confirmed_at IS NULL "
            "AND failure_note IS NOT NULL AND length(trim(failure_note)) >= 3)",
            name="ck_invoice_payment_lifecycle_state",
        ),
        Index("ix_invoice_payment_invoice_time", "hospital_id", "invoice_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    invoice_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    method: Mapped[str] = mapped_column(String(24), nullable=False)
    external_reference: Mapped[str | None] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    confirmed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
", name="ck_invoice_line_currency"),
        Index("ix_invoice_line_invoice", "hospital_id", "invoice_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    invoice_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    service_definition_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    description: Mapped[str] = mapped_column(String(240), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class InvoicePayment(Base):
    __tablename__ = "invoice_payments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "invoice_id"],
            ["invoices.hospital_id", "invoices.id"],
            name="fk_invoice_payment_invoice",
        ),
        UniqueConstraint("hospital_id", "id", name="uq_invoice_payment_hospital_id"),
        UniqueConstraint("hospital_id", "external_reference", name="uq_invoice_payment_external_reference"),
        CheckConstraint("status IN ('pending', 'confirmed', 'failed')", name="ck_invoice_payment_status"),
        CheckConstraint("amount > 0", name="ck_invoice_payment_amount"),
        CheckConstraint("method IN ('cash', 'card', 'bank_transfer', 'mobile_money', 'cheque', 'other')", name="ck_invoice_payment_method"),
        CheckConstraint("currency ~ '^[A-Z]{3}", name="ck_invoice_payment_currency"),
        CheckConstraint(
            "(status = 'pending' AND confirmed_by_user_id IS NULL AND confirmed_at IS NULL AND failure_note IS NULL) OR "
            "(status = 'confirmed' AND confirmed_by_user_id IS NOT NULL AND confirmed_at IS NOT NULL "
            "AND confirmed_by_user_id != created_by_user_id AND failure_note IS NULL) OR "
            "(status = 'failed' AND confirmed_by_user_id IS NULL AND confirmed_at IS NULL "
            "AND failure_note IS NOT NULL AND length(trim(failure_note)) >= 3)",
            name="ck_invoice_payment_lifecycle_state",
        ),
        Index("ix_invoice_payment_invoice_time", "hospital_id", "invoice_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    invoice_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    method: Mapped[str] = mapped_column(String(24), nullable=False)
    external_reference: Mapped[str | None] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    confirmed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
", name="ck_invoice_payment_currency"),
        CheckConstraint(
            "(status = 'pending' AND confirmed_by_user_id IS NULL AND confirmed_at IS NULL AND failure_note IS NULL) OR "
            "(status = 'confirmed' AND confirmed_by_user_id IS NOT NULL AND confirmed_at IS NOT NULL "
            "AND confirmed_by_user_id != created_by_user_id AND failure_note IS NULL) OR "
            "(status = 'failed' AND confirmed_by_user_id IS NULL AND confirmed_at IS NULL "
            "AND failure_note IS NOT NULL AND length(trim(failure_note)) >= 3)",
            name="ck_invoice_payment_lifecycle_state",
        ),
        Index("ix_invoice_payment_invoice_time", "hospital_id", "invoice_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    invoice_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    method: Mapped[str] = mapped_column(String(24), nullable=False)
    external_reference: Mapped[str | None] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    confirmed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
