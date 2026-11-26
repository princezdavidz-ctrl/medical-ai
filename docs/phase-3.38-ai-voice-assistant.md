# Phase 3.38 — AI Voice Assistant

## Objective
Provide a hands-free voice interface to the central Medical AI platform without creating a separate model, speech service, conversation store or authorization path.

## API
- POST /api/v1/ai/voice/turn
- Request: on-device recognized transcript and locale.
- Response: recognized transcript, concise spoken-response text, approved evidence citations, model/prompt provenance and explicit privacy/safety flags.

## Speech I/O architecture
- Speech-to-text runs on the client device/browser.
- The client sends only recognized text; raw microphone audio is never uploaded to this backend endpoint.
- Text-to-speech runs on the client device/browser using the returned text.
- The API declares both speech input and output as on-device and does not create audio files.
- No conversation history is persisted by this workflow.

## Security and safety
- Authenticated active hospital membership is required.
- The voice capability is independently allow-listed and obeys global AI request and hospital pause gates.
- Local model provider is mandatory even when system operating mode is hybrid; no hosted fallback or audio transfer is attempted.
- Direct identifiers are rejected. Patient-specific questions are outside scope and are redirected to a qualified clinician.
- Only approved current knowledge evidence can ground general medical information.
- Audit records include actor, hospital, locale, capability, outcome and citation count only; transcript and response text are excluded.
- Voice is not identity verification, consent, authorization or confirmation for clinical or operational actions.

## Explicit exclusions
- No chart access, patient-specific result interpretation, diagnosis, treatment recommendation, prescribing or dose calculations.
- No appointment booking, clinical messaging, ambulance dispatch, record mutation or other workflow execution.
- No audio upload, server-side transcription, server-side speech synthesis or conversation persistence.
- No autonomous clinical use; clinical review remains required.

## Verification
All security, privacy, local-only routing, capability, evidence, language, emergency escalation, audio boundary and device compatibility scenarios are listed in docs/TEST_REGISTER_PHASE_5.md. Backend tests remain deferred to Phase 5.
