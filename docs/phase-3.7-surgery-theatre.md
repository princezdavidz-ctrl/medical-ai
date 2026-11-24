# Phase 3.7 — Surgery & Operating Theatre

## Implemented scope

This milestone adds theatre inventory, scheduled surgical cases, team assignments, surgical safety checklists, anesthesia documentation, operative events/notes and a controlled recovery completion workflow.

### Workflow

1. A theatre manager registers an active theatre room linked to a department.
2. A surgeon with an active assignment to an in-progress encounter schedules a procedure in a theatre in the same department.
3. Scheduling locks the patient, theatre and surgeon resources and rejects overlapping cases for the same patient, surgeon or theatre. An already in-progress/recovery case blocks reuse of those resources regardless of its planned end time.
4. The lead surgeon or theatre manager assigns the theatre team. Assigned team members include surgeons, anesthesia providers and theatre nurses.
5. Assigned team members record sign-in and time-out checklist revisions. Failed checks are retained; a later passing revision does not erase the earlier failed record.
6. An assigned anesthesia provider records anesthesia type, manually entered ASA physical-status class (I–VI), airway method and pre-anesthesia assessment. Medication doses are not captured.
7. The lead surgeon can start the case only when the latest sign-in and time-out checklists pass and a valid anesthesia record exists.
8. Assigned team members append surgical events and signed notes.
9. The lead surgeon completes the procedure only after a passing sign-out checklist and a signed operative note. The case enters recovery.
10. The lead surgeon completes recovery only after a signed postoperative or handover note.
11. A scheduled case may be cancelled with a reason. A started procedure cannot be cancelled through this route.

## API routes

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/surgery/theatres` | Create theatre room |
| GET | `/api/v1/surgery/theatres` | List theatres by department scope |
| POST | `/api/v1/surgery/encounters/{encounter_id}/lead-surgeon-assignment` | Assign a lead surgeon to an encounter |
| POST | `/api/v1/surgery/cases` | Schedule a surgical case |
| GET | `/api/v1/surgery/cases` | List assigned cases or manager-visible cases |
| GET | `/api/v1/surgery/cases/{case_id}` | Read case and records |
| POST | `/api/v1/surgery/cases/{case_id}/team` | Assign theatre team member |
| POST | `/api/v1/surgery/cases/{case_id}/checklists` | Record sign-in/time-out/sign-out checklist revision |
| POST | `/api/v1/surgery/cases/{case_id}/anesthesia` | Record anesthesia assessment |
| POST | `/api/v1/surgery/cases/{case_id}/start` | Start procedure after safety gates |
| POST | `/api/v1/surgery/cases/{case_id}/events` | Append surgical event |
| POST | `/api/v1/surgery/cases/{case_id}/notes` | Sign operative/post-op/handover note |
| POST | `/api/v1/surgery/cases/{case_id}/complete-procedure` | Complete procedure and enter recovery |
| POST | `/api/v1/surgery/cases/{case_id}/complete-recovery` | Complete recovery workflow |
| POST | `/api/v1/surgery/cases/{case_id}/cancel` | Cancel a scheduled case |

## Safety and authorization

- Surgeons require an active hospital membership, an approved surgeon role and an active patient-care assignment for the encounter. Professional credential verification and privileges remain an external governance prerequisite.
- Theatre managers can manage rooms, schedules, team assignment and cancellation only within their own department; hospital administrators have hospital-wide operational scope. Full clinical case detail is restricted to assigned team members and hospital administrators.
- Team members must have a recognized surgical/anesthesia/theatre-nursing role, active same-hospital membership and an explicit assignment to the patient encounter. Cross-department assignments are permitted only through the case team workflow.
- Manager-issued lead-surgeon preassignments expire after 30 days if no case is scheduled; scheduling extends the assignment through the planned end plus a 24-hour recovery window.
- Anesthesia documentation is restricted to assigned anesthesia-provider roles.
- Failed safety checklist items can be recorded and remain in history; the case cannot start until the latest sign-in and time-out revisions pass.
- Site marking and count checks can be explicitly marked not applicable; all other required safety checks must pass.
- Procedure completion requires a passing sign-out checklist and signed operative note. Recovery completion requires a signed postoperative or handover note.
- Theatre, surgeon and patient scheduling conflicts are serialized with row locks and overlap checks.
- Hospital RLS and composite foreign keys bind cases, patients, encounters, theatre rooms and all child records to the same hospital.
- Audits record actor/action/resource without copying procedure narratives, anesthesia notes or checklist content.

## Clinical safety boundaries

- The checklist is a structured record of staff confirmation; it is not a substitute for locally approved surgical safety protocols or signed informed-consent records.
- ASA class is manually recorded; the system does not calculate or interpret it.
- No medication orders/doses, anesthesia drug dosing, ventilator settings control, blood product orders, implant/device inventory, pathology diagnosis, autonomous procedure selection or AI-generated surgical advice are enabled.
- The system records anesthesia type and airway documentation only; it does not control anesthesia equipment.
- Procedure completion and recovery completion are distinct states.
- No post-operative inpatient bed transfer, recovery-bed allocation or discharge is implied by case completion.

## Deferred integrations

- Surgical procedure catalogs and coding, specialty-specific workflows and implants.
- Blood bank, pathology/specimen chain-of-custody and laboratory/radiology orders.
- Pharmacy/anesthesia medication orders and administration.
- PACU/recovery bed inventory, inpatient ward transfer and discharge coordination.
- Theatre equipment/device integration, staffing rosters and quality dashboards.

All scheduling, checklist, anesthesia, team assignment, workflow transition, tenant, audit and safety-gate checks are in the Phase 5 Test Register. Tests have not been executed for this milestone.
