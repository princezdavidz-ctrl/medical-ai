from app.knowledge.ingestion import (
    validate_import_payload,
    validate_terminology_mapping,
    validate_unit_mapping,
)


def test_import_validation_hashes_payload_and_requires_license_review():
    payload = "Synthetic non-clinical test fixture"
    result = validate_import_payload(
        title="Synthetic source", source_identity="fixture://source-a",
        jurisdiction="KE", language="en", content_type="clinical_reference",
        payload_text=payload, declared_license="Test-only license", license_verified=True,
    )
    assert result.valid
    assert len(result.content_sha256) == 64
    blocked = validate_import_payload(
        title="Synthetic source", source_identity="fixture://source-a",
        jurisdiction="KE", language="en", content_type="clinical_reference",
        payload_text=payload, declared_license=None, license_verified=False,
    )
    assert "license_declaration_required" in blocked.errors
    assert "license_not_verified" in blocked.errors


def test_snomed_and_loinc_require_verified_license_and_release_metadata():
    errors = validate_terminology_mapping(
        code_system="SNOMED-CT", code="synthetic-code", release_version="test-release",
        jurisdiction="KE", license_verified=False, license_reference=None,
    )
    assert "terminology_license_not_verified" in errors
    assert "terminology_license_reference_required" in errors
    allowed = validate_terminology_mapping(
        code_system="LOINC", code="synthetic-code", release_version="test-release",
        jurisdiction="KE", license_verified=True, license_reference="authorized-test-reference",
    )
    assert allowed == ()


def test_unit_mapping_requires_named_review_and_does_not_infer_conversion():
    errors = validate_unit_mapping(
        source_unit="unit-A", canonical_unit="unit-B",
        source_reference="synthetic-method-reference", reviewer_user_id=None, reviewed_at=None,
    )
    assert errors == ("unit_mapping_requires_named_reviewer_and_timestamp",)
    assert validate_unit_mapping(
        source_unit="unit-A", canonical_unit="unit-A",
        source_reference="synthetic-method-reference", reviewer_user_id="reviewer-id",
        reviewed_at="reviewed-at",
    ) == ()
