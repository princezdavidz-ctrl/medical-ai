# Phase 2B.16 — AI usage accounting and subscription enforcement

## Quota model

Each hospital has a billing-period AI usage policy linked to a subscription reference and plan code. The policy defines:
- request limit;
- input-token limit;
- output-token limit;
- maximum output tokens per request;
- optional cost limit in micros of the policy currency;
- billing period start and exclusive end date;
- active, suspended or expired state.

No policy is seeded. AI requests fail closed with `ai_usage_policy_not_configured` until the trusted platform billing process provisions an active policy.

## Reservation and enforcement

Before any model call, the orchestrator:
1. Retrieves approved evidence and builds the final bounded context.
2. Estimates input tokens from the prompt and evidence context.
3. Locks the active hospital policy and usage counter.
4. Reserves one request, estimated input tokens and the maximum allowed output tokens.
5. Checks remaining request, input, output and optional cost quotas.
6. Commits the reservation before making the external/local model call.

This prevents concurrent requests from all consuming the same remaining quota. The output token cap sent to the provider is the lower of its configured maximum and the subscription policy maximum.

After a response, actual provider token counts are used when supplied; otherwise a conservative character-based estimate is recorded. Usage is settled before citation validation, so responses withheld for invalid citations are still accounted for. Provider failures release the reservation as a failed attempt and are conservatively charged against the reserved input estimate.

## Pricing and cost

Pricing is configured through `AI_MODEL_PRICING_JSON`, keyed by `provider_id:model_id`, with integer input/output micros per million tokens and a three-letter currency. The exact pricing object is snapshotted into each reservation so later price changes do not rewrite historical cost calculations.

If a plan has a cost limit but no matching model price exists, the request is blocked. If no cost limit exists and no price is configured, token usage is still enforced but monetary cost is reported as unknown (`cost_micros=null`). No model prices are invented or seeded.

## Usage ledger and dashboard

- Hospital-scoped policies, counters, reservations and usage events use forced PostgreSQL RLS.
- Usage events are append-only.
- Events record capability, mode, provider, model/version, input/output tokens, cost, currency, latency, estimate flag and outcome.
- Prompts, generated text, patient identifiers and clinical context are never stored in the usage ledger.
- `GET /api/v1/ai/usage` provides the current hospital plan counters and the latest 100 usage events. Access is limited to hospital admin, hospital director, finance manager or system admin roles.

## Expired reservations

Reservations expire after the configured `AI_USAGE_RESERVATION_TTL_SECONDS` (default 600 seconds). A bounded cleanup operation releases abandoned reservations per authenticated hospital/user context. Deployment operations must schedule this cleanup worker.

## Operational limitations

- No hospital usage policies, subscription plans or model prices are seeded.
- Policy provisioning must come from a trusted platform billing workflow; hospital users cannot raise their own quota through this API.
- The Phase 3 Billing & Finance / Hospital Administration modules will provide the governed subscription lifecycle and policy provisioning UI/API.
- Local model cost is unknown unless the operator configures an explicit cost rate; zero cost must not be assumed.
- Token counts from providers are preferred; character-based estimates are marked as estimated.
- If a provider returns more tokens than reserved, actual usage is recorded even if that pushes the period over quota; subsequent requests are blocked.
- This milestone does not activate clinical capabilities. AI execution remains disabled by default and still requires all independent clinical, legal and security approvals.
