# Phase 3.13 — Billing & Finance

## Scope implemented

Billing provides a governed hospital service/charge catalog, encounter-linked invoices, immutable invoice lines, payment recording, independent payment confirmation and invoice voiding controls.

### Workflow

1. **Service catalog drafting** — billing managers create hospital-specific service definitions with code, description, unit price and three-letter uppercase currency code. New definitions remain drafts.
2. **Independent catalog approval** — a different finance manager/director approves the draft. Active definitions can be retired with a recorded reason.
3. **Invoice drafting** — billing staff create a draft invoice against an existing hospital encounter. Patient identity is derived from the encounter; the client cannot submit an unrelated patient ID.
4. **Invoice line entry** — billing staff add approved service definitions and quantities. The server snapshots description and unit price, calculates the line total using two-decimal rounding and updates the invoice subtotal. Lines can only be inserted while the invoice is draft.
5. **Invoice issue** — a finance manager/director other than the creator issues an invoice with at least one positive-value line. Issued invoices and their lines cannot be edited through this API.
6. **Payment recording** — cashier/accounts staff record a pending payment with method and optional external reference. The system does not contact a bank, card processor or mobile-money gateway.
7. **Independent payment confirmation** — a different finance officer/manager confirms or a billing staff member marks a pending payment failed. Confirmed payments update the invoice balance. Partial and full settlement are tracked.
8. **Invoice voiding** — a finance manager/director can void a draft or issued invoice only when no amount has been paid and no pending payment remains. A reason is required.

## API routes

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/billing/service-definitions` | Create a draft service/charge definition |
| POST | `/api/v1/billing/service-definitions/{service_id}/approve` | Independently approve a service definition |
| POST | `/api/v1/billing/service-definitions/{service_id}/retire` | Retire an active definition with reason |
| GET | `/api/v1/billing/service-definitions` | List active definitions |
| POST | `/api/v1/billing/encounters/{encounter_id}/invoices` | Create a draft invoice |
| POST | `/api/v1/billing/invoices/{invoice_id}/lines` | Add a service line to a draft invoice |
| POST | `/api/v1/billing/invoices/{invoice_id}/issue` | Issue an invoice |
| GET | `/api/v1/billing/invoices` | View the department invoice queue |
| GET | `/api/v1/billing/invoices/{invoice_id}` | Read invoice, lines and payments |
| POST | `/api/v1/billing/invoices/{invoice_id}/payments` | Record a pending payment |
| POST | `/api/v1/billing/payments/{payment_id}/confirm` | Independently confirm a payment |
| POST | `/api/v1/billing/payments/{payment_id}/fail` | Mark a pending payment failed |
| POST | `/api/v1/billing/invoices/{invoice_id}/void` | Void an eligible invoice with reason |

## Authorization, tenant isolation and audit

- Service catalog creation is restricted to billing catalog roles and the billing department.
- Service approval requires a different finance manager/director from the creator.
- Invoice creation and line entry are limited to billing staff in the invoice department.
- Invoice issue requires a finance manager/director different from the invoice creator.
- Payment recording and payment confirmation are separated: the confirmer cannot be the payment creator.
- Invoice voiding is limited to finance managers/directors and requires no confirmed or pending payment.
- Composite foreign keys bind invoices to the same hospital, patient, encounter and billing department; invoice lines and payments are bound to their hospital-scoped parents.
- All billing tables enforce hospital row-level security.
- Database triggers prevent invoice-line update/delete, prevent adding lines after invoice issue, keep invoice totals synchronized, enforce service/invoice department and currency consistency, require new payments to start pending and make finalized payment records immutable.
- Audit metadata records actor, action, resource ID, currency and state values; patient names, clinical notes and clinical indications are not copied into audit metadata.
- Invoice queues expose only MRN and given/family name for patient identification.

## Financial and operational boundaries

- Currency defaults to KES but each invoice/service definition uses an explicit three-letter uppercase currency code. All lines and payments must match the invoice currency.
- Invoice numbers are generated unique identifiers, not a legally certified sequential tax-invoice numbering scheme. Production deployment must configure compliant numbering and fiscalization where required.
- The module calculates service line totals and invoice subtotals only. It does not calculate VAT, withholding tax, levies, discounts, late fees or statutory deductions.
- No service catalog, price list, tax rule or patient financial data is seeded.
- Payment records are manually entered and confirmed by finance staff. No M-Pesa, bank, card processor or other payment gateway is connected; a recorded confirmation is not proof of external settlement.
- No refunds, reversals, credit notes, write-offs, general ledger, cashbook reconciliation or accounting exports are implemented.
- No insurance claims or SHA workflows are implemented here; those belong to the Insurance & Claims module.
- No automatic charges are generated from OPD, laboratory, radiology, pharmacy, theatre or inpatient workflows. Cross-module charge capture is a Phase 4 integration.
- No live patient or financial data is seeded.

## Deferred integrations

- Kenya Revenue Authority eTIMS/fiscalization and legally compliant invoice numbering.
- M-Pesa/Daraja, card, bank, wallet and other payment gateway adapters with signed callbacks and reconciliation.
- VAT, withholding, statutory levies, discounts, deposits, credit notes, refunds and reversals.
- General ledger, accounts receivable/payable, cashbook, procurement and financial reporting.
- SHA/private insurance claims, preauthorization, remittance and reconciliation in the Insurance & Claims module.
- Charge capture from clinical modules and automated billing rules in Phase 4.
- Patient portal invoice access and online payment.

All service catalog, invoice, line calculation, currency, issue separation, payment creation/confirmation, overpayment, void, append-only history, tenant isolation and audit checks are listed in the Phase 5 Test Register. Tests have not been executed for this milestone.
