# Phase 2B.17 — Capability prompt and workflow registry

## Registry contract

The central AI platform now has one immutable, source-controlled registry entry for each capability:
- medical information;
- clinical decision support;
- laboratory interpretation;
- medication safety;
- radiology support.

Each entry contains:
- independent semantic prompt version;
- capability-specific system instructions;
- explicit tool permission list (empty for every capability until a tool is separately reviewed);
- response-envelope schema;
- workflow safety contract;
- canonical SHA-256 digest over the complete registry entry.

The registry is deliberately source-controlled in this milestone. Changes are made through reviewed Git commits and require a new prompt version. Runtime editing is not exposed to hospital users or ordinary API roles.

## Runtime enforcement

- The orchestrator resolves the capability's registered prompt before model invocation.
- Both local and hosted providers receive the same capability-specific system instructions, output contract, workflow rules and explicit tool allow-list.
- No tool execution framework is enabled; all tool permission lists are empty.
- The workflow contract explicitly prohibits autonomous diagnosis, prescribing and orders, requires evidence citations and uncertainty, and requires clinician review.
- The API response is validated against a Pydantic response model with clinical-use and clinician-review flags fixed to false/true respectively.
- Capability discovery reports prompt version, prompt digest and permitted tools.
- Every generated response and its privacy-minimal audit metadata records the prompt version and exact digest.
- AI evaluation manifests now require a prompt SHA-256 digest in addition to prompt version; the evaluation run table stores that digest. The digest is also returned in each response so a downstream evaluation harness can bind results to the exact registry content.

## Change governance

A prompt change must:
1. create a new immutable prompt version;
2. produce a new registry digest;
3. trigger new evaluations for the affected capability, model and operating mode;
4. preserve prior evaluation records for traceability;
5. receive the existing independent release approvals before clinical activation.

No prompt is claimed to be clinically validated by its presence in the registry. All capabilities remain subject to the global execution gate, empty-by-default allow-list and independent release process.

## Limitations

- Registry content is source-controlled, not editable through an administrative UI.
- No clinical tools are currently available to the model.
- The output schema validates the API response envelope; it does not make generated clinical content factually correct.
- The registry does not activate AI or authorize patient-care use.
