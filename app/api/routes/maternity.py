from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.audit import write_audit_event
from app.api.deps import get_current_context
from app.db.session import get_db
from app.models import (
    Department,
    DeliveryRecord,
    Encounter,
    HospitalMembership,
    LaborObservation,
    LaborRecord,
    MaternityAntenatalVisit,
    MaternityEpisode,
    MaternityNote,
    NewbornObservation,
    NewbornRecord,
    Patient,
    PatientCareAssignment,
    PostpartumObservation,
    Role,
    SurgicalCase,
)
from app.schemas.maternity import (
    DeliveryRecordCreate,
    DeliveryRecordRead,
    LaborObservationCreate,
    LaborObservationRead,
    LaborRecordCreate,
    LaborRecordRead,
    MaternityAntenatalVisitCreate,
    MaternityAntenatalVisitRead,
    MaternityEpisodeClose,
    MaternityEpisodeCreate,
    MaternityEpisodeDetailRead,
    MaternityEpisodeRead,
    MaternityEpisodeEnd,
    MaternityNoteCreate,
    MaternityNoteRead,
    NewbornObservationCreate,
    NewbornObservationRead,
    NewbornPatientLink,
    NewbornRecordCreate,
    NewbornRecordRead,
    PostpartumObservationCreate,
    PostpartumObservationRead,
)

router = APIRouter(prefix="/maternity", tags=["maternity and newborn care"])

_MIDWIFE_ROLES = {"midwife", "maternity_midwife", "nurse_midwife"}
_OBSTETRICIAN_ROLES = {
    "obstetrician", "gynecologist", "ob_gyn", "obgyn",
    "doctor", "physician", "medical_officer",
}
_MATERNITY_NURSE_ROLES = {
    "maternity_nurse", "nurse", "registered_nurse", "nursing_officer",
}
_NEONATAL_ROLES = {
    "neonatal_nurse", "pediatric_nurse", "pediatrician",
    "midwife", "nurse", "registered_nurse",
}
_EPISODE_ROLES = _MIDWIFE_ROLES | _OBSTETRICIAN_ROLES
_VISIT_ROLES = _MIDWIFE_ROLES | _OBSTETRICIAN_ROLES | _MATERNITY_NURSE_ROLES
_LABOR_ROLES = _MIDWIFE_ROLES | _OBSTETRICIAN_ROLES | _MATERNITY_NURSE_ROLES
_DELIVERY_ROLES = _MIDWIFE_ROLES | _OBSTETRICIAN_ROLES
_NEWBORN_ROLES = _MIDWIFE_ROLES | _OBSTETRICIAN_ROLES | _MATERNITY_NURSE_ROLES
_POSTPARTUM_ROLES = _MIDWIFE_ROLES | _OBSTETRICIAN_ROLES | _MATERNITY_NURSE_ROLES
_ADMIN_ROLES = {"hospital_admin", "hospital_director", "system_admin"}
_REGISTRATION_ROLES = {"registration_clerk", "receptionist", "medical_records_officer"}


def _membership(db: Session, *, user_id: UUID, hospital_id: UUID):
    return db.scalar(
        select(HospitalMembership)
        .join(Role, Role.id == HospitalMembership.role_id)
        .where(
            HospitalMembership.hospital_id == hospital_id,
            HospitalMembership.user_id == user_id,
            HospitalMembership.status == "active",
        )
    )


def _role_name(db: Session, membership: HospitalMembership | None) -> str:
    role = db.get(Role, membership.role_id) if membership else None
    return role.name.strip().casefold().replace(" ", "_") if role else ""


def _require_role(
    db: Session, *, user_id: UUID, hospital_id: UUID,
    allowed: set[str], department_id: UUID | None = None,
) -> tuple[HospitalMembership, str]:
    membership = _membership(db, user_id=user_id, hospital_id=hospital_id)
    role_name = _role_name(db, membership)
    if membership is None or (role_name not in allowed and role_name not in _ADMIN_ROLES):
        raise HTTPException(status_code=403, detail={"code": "maternity_role_not_authorized"})
    if role_name not in _ADMIN_ROLES and department_id is not None:
        if membership.department_id != department_id:
            raise HTTPException(status_code=403, detail={"code": "maternity_department_scope_required"})
    return membership, role_name


def _restore_tenant_context(db: Session, *, user_id: UUID, hospital_id: UUID) -> None:
    db.execute(
        text("SELECT set_config('app.current_hospital_id', :hospital_id, true)"),
        {"hospital_id": str(hospital_id)},
    )
    db.execute(
        text("SELECT set_config('app.current_user_id', :user_id, true)"),
        {"user_id": str(user_id)},
    )


def _audit(
    db: Session, *, hospital_id: UUID, user_id: UUID,
    action: str, resource_type: str, resource_id: UUID | None,
) -> None:
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user_id,
        action=action, resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
    )


def _has_assignment(
    db: Session, *, user_id: UUID, hospital_id: UUID,
    patient_id: UUID, encounter_id: UUID, department_id: UUID,
) -> bool:
    now = datetime.now(timezone.utc)
    return db.scalar(select(PatientCareAssignment.id).where(
        PatientCareAssignment.hospital_id == hospital_id,
        PatientCareAssignment.patient_id == patient_id,
        PatientCareAssignment.encounter_id == encounter_id,
        PatientCareAssignment.staff_user_id == user_id,
        PatientCareAssignment.department_id == department_id,
        PatientCareAssignment.status == "active",
        PatientCareAssignment.valid_from <= now,
        or_(
            PatientCareAssignment.valid_until.is_(None),
            PatientCareAssignment.valid_until > now,
        ),
    ).limit(1)) is not None


def _get_episode(
    db: Session, *, hospital_id: UUID, episode_id: UUID, lock: bool = False
) -> MaternityEpisode:
    query = select(MaternityEpisode).where(
        MaternityEpisode.id == episode_id,
        MaternityEpisode.hospital_id == hospital_id,
    )
    if lock:
        query = query.with_for_update()
    episode = db.scalar(query)
    if episode is None:
        raise HTTPException(status_code=404, detail={"code": "maternity_episode_not_found"})
    return episode


def _require_episode_access(
    db: Session, *, user_id: UUID, hospital_id: UUID,
    episode: MaternityEpisode, allowed: set[str],
) -> str:
    membership, role_name = _require_role(
        db, user_id=user_id, hospital_id=hospital_id,
        allowed=allowed,
    )
    if role_name not in _ADMIN_ROLES and (
        membership.department_id is None or not _has_assignment(
            db, user_id=user_id, hospital_id=hospital_id,
            patient_id=episode.patient_id, encounter_id=episode.encounter_id,
            department_id=membership.department_id,
        )
    ):
        raise HTTPException(status_code=404, detail={"code": "maternity_episode_not_found"})
    return role_name


def _get_labor(
    db: Session, *, hospital_id: UUID, labor_id: UUID, lock: bool = False
) -> LaborRecord:
    query = select(LaborRecord).where(
        LaborRecord.id == labor_id, LaborRecord.hospital_id == hospital_id
    )
    if lock:
        query = query.with_for_update()
    labor = db.scalar(query)
    if labor is None:
        raise HTTPException(status_code=404, detail={"code": "labor_record_not_found"})
    return labor


def _get_delivery(
    db: Session, *, hospital_id: UUID, delivery_id: UUID, lock: bool = False
) -> DeliveryRecord:
    query = select(DeliveryRecord).where(
        DeliveryRecord.id == delivery_id, DeliveryRecord.hospital_id == hospital_id
    )
    if lock:
        query = query.with_for_update()
    delivery = db.scalar(query)
    if delivery is None:
        raise HTTPException(status_code=404, detail={"code": "maternity_delivery_not_found"})
    return delivery


def _get_newborn(
    db: Session, *, hospital_id: UUID, newborn_id: UUID, lock: bool = False
) -> NewbornRecord:
    query = select(NewbornRecord).where(
        NewbornRecord.id == newborn_id, NewbornRecord.hospital_id == hospital_id
    )
    if lock:
        query = query.with_for_update()
    newborn = db.scalar(query)
    if newborn is None:
        raise HTTPException(status_code=404, detail={"code": "newborn_record_not_found"})
    return newborn


def _validate_delivery_surgical_case(
    db: Session, *, hospital_id: UUID, episode: MaternityEpisode,
    delivery_mode: str, surgical_case_id: UUID | None,
) -> None:
    if delivery_mode == "cesarean":
        if surgical_case_id is None:
            raise HTTPException(status_code=422, detail={"code": "cesarean_requires_surgical_case_link"})
        surgical_case = db.scalar(select(SurgicalCase).where(
            SurgicalCase.id == surgical_case_id,
            SurgicalCase.hospital_id == hospital_id,
            SurgicalCase.patient_id == episode.patient_id,
            SurgicalCase.encounter_id == episode.encounter_id,
            SurgicalCase.status.in_(("in_progress", "recovery", "completed")),
        ).with_for_update())
        if surgical_case is None:
            raise HTTPException(status_code=409, detail={"code": "matching_active_or_completed_cesarean_case_required"})
    elif surgical_case_id is not None:
        raise HTTPException(status_code=422, detail={"code": "surgical_case_link_only_allowed_for_cesarean"})


def _episode_detail(db: Session, episode: MaternityEpisode) -> dict:
    antenatal = db.scalars(select(MaternityAntenatalVisit).where(
        MaternityAntenatalVisit.hospital_id == episode.hospital_id,
        MaternityAntenatalVisit.episode_id == episode.id,
    ).order_by(MaternityAntenatalVisit.visited_at)).all()
    labor = db.scalar(select(LaborRecord).where(
        LaborRecord.hospital_id == episode.hospital_id,
        LaborRecord.episode_id == episode.id,
    ))
    labor_observations = []
    if labor is not None:
        labor_observations = db.scalars(select(LaborObservation).where(
            LaborObservation.hospital_id == episode.hospital_id,
            LaborObservation.labor_record_id == labor.id,
        ).order_by(LaborObservation.observed_at)).all()
    delivery = db.scalar(select(DeliveryRecord).where(
        DeliveryRecord.hospital_id == episode.hospital_id,
        DeliveryRecord.episode_id == episode.id,
    ))
    newborns = []
    if delivery is not None:
        newborns = db.scalars(select(NewbornRecord).where(
            NewbornRecord.hospital_id == episode.hospital_id,
            NewbornRecord.delivery_id == delivery.id,
        ).order_by(NewbornRecord.birth_order)).all()
    postpartum = db.scalars(select(PostpartumObservation).where(
        PostpartumObservation.hospital_id == episode.hospital_id,
        PostpartumObservation.episode_id == episode.id,
    ).order_by(PostpartumObservation.observed_at)).all()
    notes = db.scalars(select(MaternityNote).where(
        MaternityNote.hospital_id == episode.hospital_id,
        MaternityNote.episode_id == episode.id,
    ).order_by(MaternityNote.signed_at)).all()
    return {
        "episode": episode,
        "antenatal_visits": antenatal,
        "labor": labor,
        "labor_observations": labor_observations,
        "delivery": delivery,
        "newborns": newborns,
        "postpartum_observations": postpartum,
        "notes": notes,
    }


@router.post("/episodes", response_model=MaternityEpisodeRead, status_code=status.HTTP_201_CREATED)
def create_maternity_episode(
    payload: MaternityEpisodeCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> MaternityEpisode:
    user, hospital_id = context
    _require_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_EPISODE_ROLES, department_id=payload.department_id,
    )
    patient = db.scalar(select(Patient).where(
        Patient.id == payload.patient_id,
        Patient.hospital_id == hospital_id,
        Patient.status == "active",
    ).with_for_update())
    if patient is None:
        raise HTTPException(status_code=404, detail={"code": "active_maternity_patient_not_found"})
    encounter = db.scalar(select(Encounter).where(
        Encounter.id == payload.encounter_id,
        Encounter.hospital_id == hospital_id,
    ).with_for_update())
    if (
        encounter is None or encounter.patient_id != patient.id
        or encounter.status != "in_progress"
        or encounter.department_id != payload.department_id
    ):
        raise HTTPException(status_code=409, detail={"code": "active_maternity_encounter_required"})
    department = db.scalar(select(Department).where(
        Department.id == payload.department_id,
        Department.hospital_id == hospital_id,
        Department.status == "active",
    ))
    if department is None:
        raise HTTPException(status_code=404, detail={"code": "active_maternity_department_not_found"})
    if not _has_assignment(
        db, user_id=user.id, hospital_id=hospital_id,
        patient_id=patient.id, encounter_id=encounter.id,
        department_id=department.id,
    ):
        raise HTTPException(status_code=403, detail={"code": "assigned_maternity_patient_required"})
    episode = MaternityEpisode(
        hospital_id=hospital_id,
        created_by_user_id=user.id,
        pregnancy_status="antenatal",
        status="active",
        **payload.model_dump(),
    )
    db.add(episode)
    try:
        db.flush()
        _audit(db, hospital_id=hospital_id, user_id=user.id,
               action="maternity.episode.created", resource_type="maternity_episode", resource_id=episode.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "active_pregnancy_or_pregnancy_number_conflict"}) from None
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(episode)
    return episode


@router.get("/episodes", response_model=list[MaternityEpisodeRead])
def list_maternity_episodes(
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
    episode_status: str | None = Query(default=None, alias="status", max_length=24),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[MaternityEpisode]:
    user, hospital_id = context
    membership, role_name = _require_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_EPISODE_ROLES | _VISIT_ROLES | _NEONATAL_ROLES,
    )
    query = select(MaternityEpisode).where(MaternityEpisode.hospital_id == hospital_id)
    if role_name not in _ADMIN_ROLES:
        now = datetime.now(timezone.utc)
        assigned_encounters = select(PatientCareAssignment.encounter_id).where(
            PatientCareAssignment.hospital_id == hospital_id,
            PatientCareAssignment.staff_user_id == user.id,
            PatientCareAssignment.department_id == membership.department_id,
            PatientCareAssignment.status == "active",
            PatientCareAssignment.valid_from <= now,
            or_(
                PatientCareAssignment.valid_until.is_(None),
                PatientCareAssignment.valid_until > now,
            ),
        )
        query = query.where(MaternityEpisode.encounter_id.in_(assigned_encounters))
    if episode_status is not None:
        query = query.where(MaternityEpisode.status == episode_status)
    episodes = list(db.scalars(
        query.order_by(MaternityEpisode.created_at.desc()).limit(limit).offset(offset)
    ).all())
    _audit(db, hospital_id=hospital_id, user_id=user.id,
           action="maternity.episodes.viewed", resource_type="maternity_episode_list", resource_id=None)
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    return episodes


@router.get("/episodes/{episode_id}", response_model=MaternityEpisodeDetailRead)
def get_maternity_episode(
    episode_id: UUID,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> dict:
    user, hospital_id = context
    episode = _get_episode(db, hospital_id=hospital_id, episode_id=episode_id)
    _require_episode_access(
        db, user_id=user.id, hospital_id=hospital_id,
        episode=episode, allowed=_EPISODE_ROLES | _VISIT_ROLES | _NEONATAL_ROLES,
    )
    result = _episode_detail(db, episode)
    _audit(db, hospital_id=hospital_id, user_id=user.id,
           action="maternity.episode.viewed", resource_type="maternity_episode", resource_id=episode.id)
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    return result


@router.post(
    "/episodes/{episode_id}/antenatal-visits",
    response_model=MaternityAntenatalVisitRead,
    status_code=status.HTTP_201_CREATED,
)
def record_antenatal_visit(
    episode_id: UUID,
    payload: MaternityAntenatalVisitCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> MaternityAntenatalVisit:
    user, hospital_id = context
    episode = _get_episode(db, hospital_id=hospital_id, episode_id=episode_id, lock=True)
    _require_episode_access(
        db, user_id=user.id, hospital_id=hospital_id,
        episode=episode, allowed=_VISIT_ROLES,
    )
    if episode.status != "active" or episode.pregnancy_status != "antenatal":
        raise HTTPException(status_code=409, detail={"code": "antenatal_episode_not_open"})
    if payload.visited_at < episode.created_at:
        raise HTTPException(status_code=422, detail={"code": "antenatal_visit_before_episode"})
    visit = MaternityAntenatalVisit(
        hospital_id=hospital_id, episode_id=episode.id,
        provider_user_id=user.id, **payload.model_dump(),
    )
    db.add(visit)
    db.flush()
    _audit(db, hospital_id=hospital_id, user_id=user.id,
           action="maternity.antenatal_visit.recorded", resource_type="maternity_antenatal_visit", resource_id=visit.id)
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(visit)
    return visit


@router.post(
    "/episodes/{episode_id}/labor",
    response_model=LaborRecordRead,
    status_code=status.HTTP_201_CREATED,
)
def start_labor(
    episode_id: UUID,
    payload: LaborRecordCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> LaborRecord:
    user, hospital_id = context
    episode = _get_episode(db, hospital_id=hospital_id, episode_id=episode_id, lock=True)
    _require_episode_access(
        db, user_id=user.id, hospital_id=hospital_id,
        episode=episode, allowed=_EPISODE_ROLES,
    )
    if episode.status != "active" or episode.pregnancy_status != "antenatal":
        raise HTTPException(status_code=409, detail={"code": "maternity_episode_not_eligible_for_labor"})
    if payload.started_at < episode.created_at:
        raise HTTPException(status_code=422, detail={"code": "labor_start_before_maternity_episode"})
    labor = LaborRecord(
        hospital_id=hospital_id,
        episode_id=episode.id,
        lead_midwife_user_id=user.id,
        status="latent",
        **payload.model_dump(),
    )
    db.add(labor)
    episode.pregnancy_status = "in_labor"
    try:
        db.flush()
        _audit(db, hospital_id=hospital_id, user_id=user.id,
               action="maternity.labor.started", resource_type="labor_record", resource_id=labor.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "labor_record_already_exists"}) from None
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(labor)
    return labor


@router.post(
    "/labor/{labor_id}/observations",
    response_model=LaborObservationRead,
    status_code=status.HTTP_201_CREATED,
)
def record_labor_observation(
    labor_id: UUID,
    payload: LaborObservationCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> LaborObservation:
    user, hospital_id = context
    labor = _get_labor(db, hospital_id=hospital_id, labor_id=labor_id, lock=True)
    episode = _get_episode(db, hospital_id=hospital_id, episode_id=labor.episode_id, lock=True)
    _require_episode_access(
        db, user_id=user.id, hospital_id=hospital_id,
        episode=episode, allowed=_LABOR_ROLES,
    )
    if (
        episode.status != "active" or episode.pregnancy_status != "in_labor"
        or labor.status not in {"latent", "active", "second_stage"}
    ):
        raise HTTPException(status_code=409, detail={"code": "labor_record_not_open"})
    if payload.observed_at < labor.started_at:
        raise HTTPException(status_code=422, detail={"code": "labor_observation_before_labor_start"})
    observation = LaborObservation(
        hospital_id=hospital_id,
        labor_record_id=labor.id,
        recorded_by_user_id=user.id,
        **payload.model_dump(),
    )
    db.add(observation)
    labor.status = payload.labor_stage
    if payload.membrane_status is not None:
        labor.membrane_status = payload.membrane_status
    db.flush()
    _audit(db, hospital_id=hospital_id, user_id=user.id,
           action="maternity.labor_observation.recorded", resource_type="labor_observation", resource_id=observation.id)
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(observation)
    return observation


@router.post(
    "/labor/{labor_id}/delivery",
    response_model=DeliveryRecordRead,
    status_code=status.HTTP_201_CREATED,
)
def record_delivery(
    labor_id: UUID,
    payload: DeliveryRecordCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> DeliveryRecord:
    user, hospital_id = context
    labor = _get_labor(db, hospital_id=hospital_id, labor_id=labor_id, lock=True)
    episode = _get_episode(db, hospital_id=hospital_id, episode_id=labor.episode_id, lock=True)
    _require_episode_access(
        db, user_id=user.id, hospital_id=hospital_id,
        episode=episode, allowed=_DELIVERY_ROLES,
    )
    if (
        episode.status != "active" or episode.pregnancy_status != "in_labor"
        or labor.status not in {"latent", "active", "second_stage"}
    ):
        raise HTTPException(status_code=409, detail={"code": "labor_not_eligible_for_delivery"})
    if payload.delivered_at < labor.started_at:
        raise HTTPException(status_code=422, detail={"code": "delivery_before_labor_start"})
    _validate_delivery_surgical_case(
        db, hospital_id=hospital_id, episode=episode,
        delivery_mode=payload.delivery_mode, surgical_case_id=payload.surgical_case_id,
    )
    delivery = DeliveryRecord(
        hospital_id=hospital_id,
        labor_record_id=labor.id,
        episode_id=episode.id,
        mother_patient_id=episode.patient_id,
        delivered_by_user_id=user.id,
        **payload.model_dump(),
    )
    db.add(delivery)
    labor.status = "delivered"
    labor.ended_at = payload.delivered_at
    episode.pregnancy_status = "postpartum"
    try:
        db.flush()
        _audit(db, hospital_id=hospital_id, user_id=user.id,
               action="maternity.delivery.recorded", resource_type="maternity_delivery", resource_id=delivery.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "delivery_already_recorded"}) from None
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(delivery)
    return delivery


@router.post(
    "/episodes/{episode_id}/delivery",
    response_model=DeliveryRecordRead,
    status_code=status.HTTP_201_CREATED,
)
def record_planned_cesarean_delivery(
    episode_id: UUID,
    payload: DeliveryRecordCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> DeliveryRecord:
    user, hospital_id = context
    episode = _get_episode(db, hospital_id=hospital_id, episode_id=episode_id, lock=True)
    _require_episode_access(
        db, user_id=user.id, hospital_id=hospital_id,
        episode=episode, allowed=_DELIVERY_ROLES,
    )
    if episode.status != "active" or episode.pregnancy_status != "antenatal":
        raise HTTPException(status_code=409, detail={"code": "maternity_episode_not_eligible_for_planned_delivery"})
    if payload.delivery_mode != "cesarean":
        raise HTTPException(status_code=422, detail={"code": "no_labor_delivery_must_be_cesarean"})
    _validate_delivery_surgical_case(
        db, hospital_id=hospital_id, episode=episode,
        delivery_mode=payload.delivery_mode, surgical_case_id=payload.surgical_case_id,
    )
    existing_labor = db.scalar(select(LaborRecord.id).where(
        LaborRecord.hospital_id == hospital_id,
        LaborRecord.episode_id == episode.id,
    ))
    existing_delivery = db.scalar(select(DeliveryRecord.id).where(
        DeliveryRecord.hospital_id == hospital_id,
        DeliveryRecord.episode_id == episode.id,
    ))
    if existing_labor is not None or existing_delivery is not None:
        raise HTTPException(status_code=409, detail={"code": "planned_cesarean_requires_no_existing_labor_or_delivery"})
    if payload.delivered_at < episode.created_at:
        raise HTTPException(status_code=422, detail={"code": "delivery_before_maternity_episode"})
    delivery = DeliveryRecord(
        hospital_id=hospital_id,
        labor_record_id=None,
        episode_id=episode.id,
        mother_patient_id=episode.patient_id,
        delivered_by_user_id=user.id,
        **payload.model_dump(),
    )
    db.add(delivery)
    episode.pregnancy_status = "postpartum"
    try:
        db.flush()
        _audit(db, hospital_id=hospital_id, user_id=user.id,
               action="maternity.planned_cesarean.recorded", resource_type="maternity_delivery", resource_id=delivery.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "delivery_already_recorded"}) from None
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(delivery)
    return delivery


@router.post(
    "/deliveries/{delivery_id}/newborns",
    response_model=NewbornRecordRead,
    status_code=status.HTTP_201_CREATED,
)
def record_newborn(
    delivery_id: UUID,
    payload: NewbornRecordCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> NewbornRecord:
    user, hospital_id = context
    delivery = _get_delivery(db, hospital_id=hospital_id, delivery_id=delivery_id, lock=True)
    episode = _get_episode(db, hospital_id=hospital_id, episode_id=delivery.episode_id, lock=True)
    _require_episode_access(
        db, user_id=user.id, hospital_id=hospital_id,
        episode=episode, allowed=_NEWBORN_ROLES,
    )
    if episode.status != "active" or episode.pregnancy_status != "postpartum":
        raise HTTPException(status_code=409, detail={"code": "maternity_episode_not_open_for_newborn_records"})
    if payload.birth_at < delivery.delivered_at:
        raise HTTPException(status_code=422, detail={"code": "newborn_birth_before_delivery_record"})
    newborn = NewbornRecord(
        hospital_id=hospital_id,
        delivery_id=delivery.id,
        mother_patient_id=episode.patient_id,
        **payload.model_dump(),
    )
    db.add(newborn)
    try:
        db.flush()
        _audit(db, hospital_id=hospital_id, user_id=user.id,
               action="maternity.newborn.recorded", resource_type="maternity_newborn", resource_id=newborn.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "newborn_birth_order_conflict"}) from None
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(newborn)
    return newborn


@router.post("/newborns/{newborn_id}/link-patient", response_model=NewbornRecordRead)
def link_newborn_patient(
    newborn_id: UUID,
    payload: NewbornPatientLink,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> NewbornRecord:
    user, hospital_id = context
    _require_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_REGISTRATION_ROLES,
    )
    newborn = _get_newborn(db, hospital_id=hospital_id, newborn_id=newborn_id, lock=True)
    if newborn.outcome == "stillbirth":
        raise HTTPException(status_code=409, detail={"code": "stillbirth_cannot_be_linked_to_patient"})
    if newborn.newborn_patient_id is not None:
        raise HTTPException(status_code=409, detail={"code": "newborn_patient_already_linked"})
    patient = db.scalar(select(Patient).where(
        Patient.id == payload.patient_id,
        Patient.hospital_id == hospital_id,
        Patient.status == "active",
    ).with_for_update())
    if patient is None:
        raise HTTPException(status_code=404, detail={"code": "newborn_patient_not_found"})
    if patient.date_of_birth != newborn.birth_at.date():
        raise HTTPException(status_code=422, detail={"code": "newborn_patient_birth_date_mismatch"})
    expected_sex = newborn.sex
    if (
        expected_sex in {"female", "male"}
        and patient.administrative_sex not in {None, expected_sex}
    ):
        raise HTTPException(status_code=422, detail={"code": "newborn_patient_sex_mismatch"})
    newborn.newborn_patient_id = patient.id
    _audit(db, hospital_id=hospital_id, user_id=user.id,
           action="maternity.newborn_patient.linked", resource_type="maternity_newborn", resource_id=newborn.id)
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(newborn)
    return newborn


@router.post(
    "/episodes/{episode_id}/postpartum-observations",
    response_model=PostpartumObservationRead,
    status_code=status.HTTP_201_CREATED,
)
def record_postpartum_observation(
    episode_id: UUID,
    payload: PostpartumObservationCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> PostpartumObservation:
    user, hospital_id = context
    episode = _get_episode(db, hospital_id=hospital_id, episode_id=episode_id, lock=True)
    _require_episode_access(
        db, user_id=user.id, hospital_id=hospital_id,
        episode=episode, allowed=_POSTPARTUM_ROLES,
    )
    if episode.status != "active" or episode.pregnancy_status != "postpartum":
        raise HTTPException(status_code=409, detail={"code": "maternity_episode_not_postpartum"})
    delivery = db.scalar(select(DeliveryRecord).where(
        DeliveryRecord.hospital_id == hospital_id,
        DeliveryRecord.episode_id == episode.id,
    ))
    if delivery is None or payload.observed_at < delivery.delivered_at:
        raise HTTPException(status_code=422, detail={"code": "postpartum_observation_before_delivery"})
    observation = PostpartumObservation(
        hospital_id=hospital_id, episode_id=episode.id,
        recorded_by_user_id=user.id, **payload.model_dump(),
    )
    db.add(observation)
    db.flush()
    _audit(db, hospital_id=hospital_id, user_id=user.id,
           action="maternity.postpartum_observation.recorded", resource_type="postpartum_observation", resource_id=observation.id)
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(observation)
    return observation


@router.post(
    "/newborns/{newborn_id}/observations",
    response_model=NewbornObservationRead,
    status_code=status.HTTP_201_CREATED,
)
def record_newborn_observation(
    newborn_id: UUID,
    payload: NewbornObservationCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> NewbornObservation:
    user, hospital_id = context
    newborn = _get_newborn(db, hospital_id=hospital_id, newborn_id=newborn_id, lock=True)
    delivery = _get_delivery(db, hospital_id=hospital_id, delivery_id=newborn.delivery_id)
    episode = _get_episode(db, hospital_id=hospital_id, episode_id=delivery.episode_id)
    _require_episode_access(
        db, user_id=user.id, hospital_id=hospital_id,
        episode=episode, allowed=_NEONATAL_ROLES,
    )
    if episode.status != "active" or newborn.outcome != "live_birth":
        raise HTTPException(status_code=409, detail={"code": "newborn_not_eligible_for_observation"})
    if payload.observed_at < newborn.birth_at:
        raise HTTPException(status_code=422, detail={"code": "newborn_observation_before_birth"})
    observation = NewbornObservation(
        hospital_id=hospital_id, newborn_record_id=newborn.id,
        recorded_by_user_id=user.id, **payload.model_dump(),
    )
    db.add(observation)
    db.flush()
    _audit(db, hospital_id=hospital_id, user_id=user.id,
           action="maternity.newborn_observation.recorded", resource_type="newborn_observation", resource_id=observation.id)
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(observation)
    return observation


@router.post(
    "/episodes/{episode_id}/notes",
    response_model=MaternityNoteRead,
    status_code=status.HTTP_201_CREATED,
)
def create_maternity_note(
    episode_id: UUID,
    payload: MaternityNoteCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> MaternityNote:
    user, hospital_id = context
    episode = _get_episode(db, hospital_id=hospital_id, episode_id=episode_id, lock=True)
    _require_episode_access(
        db, user_id=user.id, hospital_id=hospital_id,
        episode=episode, allowed=_EPISODE_ROLES | _VISIT_ROLES | _NEONATAL_ROLES,
    )
    if episode.status != "active":
        raise HTTPException(status_code=409, detail={"code": "maternity_episode_closed"})
    note = MaternityNote(
        hospital_id=hospital_id, episode_id=episode.id,
        author_user_id=user.id, **payload.model_dump(),
    )
    db.add(note)
    db.flush()
    _audit(db, hospital_id=hospital_id, user_id=user.id,
           action="maternity.note.signed", resource_type="maternity_note", resource_id=note.id)
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(note)
    return note


@router.post("/episodes/{episode_id}/end-pregnancy", response_model=MaternityEpisodeRead)
def end_pregnancy(
    episode_id: UUID,
    payload: MaternityEpisodeEnd,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> MaternityEpisode:
    user, hospital_id = context
    episode = _get_episode(db, hospital_id=hospital_id, episode_id=episode_id, lock=True)
    _require_episode_access(
        db, user_id=user.id, hospital_id=hospital_id,
        episode=episode, allowed=_OBSTETRICIAN_ROLES,
    )
    if episode.status != "active" or episode.pregnancy_status not in {"antenatal", "in_labor"}:
        raise HTTPException(status_code=409, detail={"code": "pregnancy_not_open_for_ending"})
    labor = db.scalar(select(LaborRecord).where(
        LaborRecord.hospital_id == hospital_id,
        LaborRecord.episode_id == episode.id,
    ).with_for_update())
    if labor is not None:
        if labor.status in {"delivered", "ended"}:
            raise HTTPException(status_code=409, detail={"code": "labor_already_ended"})
        labor.status = "ended"
        labor.ended_at = datetime.now(timezone.utc)
    now = datetime.now(timezone.utc)
    episode.pregnancy_status = "ended"
    episode.pregnancy_end_reason = payload.reason
    episode.status = "closed"
    episode.closed_at = now
    episode.closed_reason = payload.note
    note = MaternityNote(
        hospital_id=hospital_id,
        episode_id=episode.id,
        author_user_id=user.id,
        note_type="other",
        note_text=payload.note,
    )
    db.add(note)
    _audit(db, hospital_id=hospital_id, user_id=user.id,
           action="maternity.pregnancy.ended", resource_type="maternity_episode", resource_id=episode.id)
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(episode)
    return episode


@router.post("/episodes/{episode_id}/close", response_model=MaternityEpisodeRead)
def close_maternity_episode(
    episode_id: UUID,
    payload: MaternityEpisodeClose,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> MaternityEpisode:
    user, hospital_id = context
    episode = _get_episode(db, hospital_id=hospital_id, episode_id=episode_id, lock=True)
    _require_episode_access(
        db, user_id=user.id, hospital_id=hospital_id,
        episode=episode, allowed=_EPISODE_ROLES,
    )
    if episode.status != "active" or episode.pregnancy_status != "postpartum":
        raise HTTPException(status_code=409, detail={"code": "only_postpartum_episode_can_be_closed"})
    labor = db.scalar(select(LaborRecord).where(
        LaborRecord.hospital_id == hospital_id,
        LaborRecord.episode_id == episode.id,
    ))
    if labor is not None and labor.status != "delivered":
        raise HTTPException(status_code=409, detail={"code": "labor_must_be_completed_before_episode_close"})
    episode.status = "closed"
    episode.closed_at = datetime.now(timezone.utc)
    episode.closed_reason = payload.reason
    _audit(db, hospital_id=hospital_id, user_id=user.id,
           action="maternity.episode.closed", resource_type="maternity_episode", resource_id=episode.id)
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(episode)
    return episode
