# AGENT.md - Tripletex AI Agent Runbook

## Overview
This service exposes a small HTTP API for the Tripletex competition agent.
It accepts a natural-language task, uses the provided Tripletex credentials, performs API calls against the provided `base_url`, and returns a completion result.

Core workflow:
`parse -> plan -> execute -> verify`

Primary code paths:
- `main.py` -> FastAPI endpoints
- `agent.py` -> task classification, parsing, orchestration, verification
- `tripletex_client.py` -> Tripletex REST wrapper
- `schemas.py` -> request/response models

## Current State

### Exposed endpoints
- `GET /health`
- `POST /solve`

### Current `/solve` contract
Request shape currently matches `schemas.py`:

```json
{
  "prompt": "Create customer Acme AS",
  "files": [
    {
      "filename": "example.pdf",
      "content_base64": "...",
      "mime_type": "application/pdf"
    }
  ],
  "tripletex_credentials": {
    "base_url": "https://<provided-base-url>/v2",
    "session_token": "<session-token>"
  }
}
```

Current response shape from `main.py`:

```json
{
  "status": "completed",
  "message": "...",
  "debug": {}
}
```

Development debug now also includes:
- the original `prompt`
- `normalized_prompt` after the parser's language-normalization step
- `task_type`
- `plan_steps` with the chosen internal actions and extracted params
- unsupported metadata such as `unsupported=true`, `implemented=false`, and `unsupported_task_type` when relevant

Competition minimum remains:

```json
{"status":"completed"}
```

Important:
- `tripletex_credentials.base_url` must come from the request and must be used for all Tripletex API calls.
- Do not rely on hardcoded sandbox URLs or tokens.
- Local helper scripts should read sandbox host/token from environment variables or request payloads; repository files should not contain live session tokens.
- `files[].mime_type` is now accepted by `schemas.py` and preserved in attachment metadata, and attachments now have limited execution impact via narrow fallback paths.
- The direct team sandbox base URL is `https://kkpqfuj-amager.tripletex.dev/v2`.
- Earlier development also used a separate proxy-style base URL, `https://api-tripletex.smaart.io/v2`; these should not be treated as interchangeable.

## Current Capabilities
- Customer creation is implemented.
- Customer creation can now derive missing `name` and `email` from the first text-like attachment when the prompt refers to an attached file instead of inline fields.
- Customer email update is implemented in a first version.
- Customer deletion is implemented in a first version.
- Department number update is implemented in a first version.
- Department deletion is implemented in a first version.
- Project customer-link update is implemented in a first version.
- Project deletion is implemented in a first version.
- Product creation is implemented.
- Product description update is implemented in a first version.
- Product deletion is implemented in a first version.
- Travel expense creation is implemented in a first version using a minimal verified payload.
- Travel expense title update is implemented in a first version.
- Travel expense deletion is implemented in a first version.
- Travel expense creation can now derive the title from the first attached filename when the prompt only refers generically to an attached receipt/file.
- Department creation is implemented.
- Project creation is implemented.
- Order creation is implemented, including creating one order line.
- Order deletion is implemented in a first version using customer and product matching.
- Invoice creation is implemented in a first version by creating an order, adding one order line, and invoicing that order.
- Employee creation is implemented in a first version, including optional account-administrator entitlement grant via Tripletex entitlement templates.
- Attachments are decoded from base64 and saved to `attachments/`.
- Attachment metadata currently preserves `filename`, saved `path`, and optional `mime_type`.
- Tripletex API calls use Basic Auth with username `0` and password `session_token`.
- Tripletex API calls now use `requests` first and can fall back to `curl` on DNS/name-resolution failures in the local Python runtime.
- Basic result verification exists for implemented create flows by reading back created resources.

## Known Gaps
- Prompt parsing is still mostly keyword and regex based, but now includes a first-pass normalization layer for common command phrases, entity names, and a few role/task phrases in Norwegian, English, Nynorsk, Spanish, Portuguese, German, and French.
- Employee name extraction now supports accented Latin characters in simple two-part names.
- Employee admin handling currently relies on the `ALL_PRIVILEGES` entitlement template instead of a narrower, task-specific entitlement set.
- Employee creation currently depends on reusing an existing active department as the default department.
- Attachments are still only used in a narrow way; travel expense create can derive a title from the first attachment filename, and customer create can read labeled `customer/name` plus `email` fields from the first text-like attachment, but general PDF/image interpretation is still missing.
- Update support is still narrow; customer email update, department number update, project customer-link update, and product description update are implemented in first versions.
- Delete support is still narrow; customer deletion, department deletion, product deletion, project deletion, and order deletion are implemented in first versions.
- Payment, credit note, and voucher/correction workflows are not implemented.
- Unsupported destructive invoice prompts are now classified as invoice-related unsupported work instead of being allowed to fall through to customer-delete matching.
- Unsupported payment, credit note, and voucher prompts are now classified explicitly so they do not fall through into create/delete handlers for other entities.
- Unsupported categories now return explicit category-specific messages and debug metadata instead of only a generic unsupported response.
- Unsupported category handling is now covered by multilingual regression tests for payment, credit note, voucher, and invoice-delete phrasing.
- Unsupported category handling also recognizes several localized synonyms such as Spanish `pago`/`abono`, Portuguese `lancamento`, French `écriture`, and German `Buchung`.
- Unsupported update/delete operations for otherwise supported entities now also fail explicitly for `invoice update`, `order update`, `employee update`, and `employee delete`.
- Local startup is not currently self-verifying; imports fail if required Python packages are not installed.
- Some local environments may resolve the sandbox host in `curl` but not in Python socket/`requests`; the client now has a DNS-failure fallback path for that case.

## Active Implementation Priorities

### Milestone 1: Stable and safe baseline
- Ensure dependency/bootstrap reliability for local and container startup.
- Keep `/health` and `/solve` as the intended public API surface.
- Keep the request/response contract explicit and minimal.

### Milestone 2: Broader task coverage
- Refine employee creation and narrow the entitlement strategy if the scoring task requires a more specific admin role setup.
- Add broader task support beyond create-only flows.
- Expand update support beyond the current customer-email path.
- Expand update support beyond customer email, department number, and product description.
- Expand delete support beyond the current product-delete path.
- Expand delete support beyond customer, department, product, and project.
- Expand the new invoice flow beyond the current single-order, single-line happy path.
- Expand order handling beyond the current create and customer-plus-product delete flows.
- Strengthen prompt understanding beyond the current phrase-normalization plus regex approach.
- Improve verification so each workflow confirms the expected end state with targeted GET calls.

## Operational Notes
- The project is currently a prototype, not a full competition-ready agent.
- FastAPI dependencies must be installed before local startup.
- Docker uses `uvicorn main:app --host 0.0.0.0 --port 8080`.
- Local baseline checks currently cover `/health`, `SolveFile` schema parsing, and attachment metadata preservation.
- The current code returns extra `message` and `debug` fields; this is acceptable for development, but the competition contract should remain compatible with `{"status":"completed"}`.
- The Tripletex client now treats successful empty HTTP bodies as valid success responses, which is important for template-style write endpoints.
- Real sandbox verification showed that employee creation requires `department.id`, so the current implementation resolves a default active department before creating employees.
- Account-administrator verification currently checks for admin entitlement names such as `ROLE_ADMINISTRATOR` and `AUTH_COMPANY_ADMIN`.
- Real sandbox verification showed that order creation requires `deliveryDate`, so the client now sends `deliveryDate` equal to `orderDate`.
- Invoice creation now ensures that the sandbox invoice bank account has a bank account number before invoicing.
- Sandbox verification showed that updating ledger account `1920` with a bank account number unblocks invoice creation.
- Project update currently uses a `[BETA]` Tripletex endpoint and should be treated as slightly higher risk than the other CRUD flows.
- Project delete currently uses the same `[BETA]` project surface and should be treated as slightly higher risk than the other CRUD flows.
- Travel expense creation currently uses a minimal payload with default employee and simple travel details, based on sandbox-verified behavior.
- Travel expense update and delete currently depend on resolving the default employee and finding expenses by title.
- Attachment-aware execution is currently limited to two narrow fallbacks: travel expense create title derivation from the first saved attachment filename, and customer create field derivation from the first text-like attachment when the prompt only references an attachment.
- Text-like attachment parsing only runs when the saved bytes look mostly printable; binary PDFs/images are ignored unless another specialized fallback is added later.
- Failed write calls hurt competition efficiency. Prefer deterministic flows and verify with GET calls before adding new writes.
- The Tripletex client now falls back to `curl` for HTTP calls when Python `requests` fails on DNS/name resolution, which is intended as an environment-level resilience measure rather than a primary transport.
- Prompt normalization now translates a small set of verbs, entity words, connector phrases, and selected task phrases such as travel-expense and account-administrator wording from Spanish, Portuguese, French, German, and Nynorsk into the existing English/Norwegian parser surface before classification and extraction.
- Task classification now uses word/phrase boundary matching instead of raw substring checks, which reduces false positives caused by entity names.
- Explicit unsupported classification is used for invoice-delete prompts so they do not collide with generic customer-delete parsing.
- Explicit unsupported classification is also used for payment, credit note, and voucher prompts so unsupported categories fail safely instead of misrouting.
- Explicit unsupported classification is also used for nearby but unimplemented operations such as invoice/order/employee update-delete flows, to prevent fallback into customer handlers.
- Unsupported categories currently return `debug.unsupported=true` and the detected unsupported task type, which makes it easier to distinguish "not implemented yet" from parser failure.
- `solve()` now also exposes `normalized_prompt` in debug output, which makes parser behavior easier to inspect during local development and test runs.
- Failed `solve()` responses now preserve `task_type` and `plan_steps` when planning succeeded, which makes execution failures easier to debug.
- Order delete currently uses a narrow `find customer -> list orders -> inspect order lines -> DELETE /order/{id}` flow to avoid ambiguous deletions.
- Keep sandbox credentials and proxy credentials separate during debugging; always trust the `tripletex_credentials.base_url` passed into the request over any remembered environment-specific URL.

## Decision Log
- `AGENT.md` is a living runbook, not a full architecture spec.
- The document should describe current behavior first, planned work second.
- Important implementation decisions may be recorded here before code lands, but they must be labeled clearly as planned.
- `process.md` is the active implementation plan baseline and should stay aligned with this file.
- Baseline cleanup removed hardcoded debug credentials and the non-essential debug endpoint from `main.py`.
- `SolveRequest.files[]` now includes optional `mime_type`, and saved attachment metadata keeps that value for later attachment-driven workflows.
- Added basic local regression tests for `/health`, schema parsing, and attachment metadata handling.
- Employee creation now uses Tripletex `userType` plus the entitlement template endpoint for account-administrator requests.
- The Tripletex client now accepts empty success bodies for write calls that do not return JSON payloads.
- Employee creation now injects a default active department because Tripletex rejects employee creation without `department.id`.
- Invoice creation now uses a deterministic `order -> order line -> invoice` flow with `sendToCustomer=false`.
- Invoice creation now includes a preflight step that ensures the invoice ledger bank account has a bank account number in sandbox.
- Customer update now supports a deterministic `find customer -> PUT /customer/{id} -> verify email` flow.
- Customer delete now supports a deterministic `find customer -> DELETE /customer/{id} -> verify absence` flow.
- Department update now supports a deterministic `find department -> PUT /department/{id} -> verify department number` flow.
- Department delete now supports a deterministic `find department -> DELETE /department/{id} -> verify absence` flow.
- Project update now supports a deterministic `find project -> PUT /project/{id} -> verify customer link` flow.
- Project delete now supports a deterministic `find project -> DELETE /project/{id} -> verify absence` flow.
- Order delete now supports a deterministic `find customer -> GET /order -> GET /order/orderline -> DELETE /order/{id} -> verify absence` flow.
- The Tripletex client now retries via `curl` when Python HTTP calls fail on DNS/name resolution, to keep local execution working in environments where `curl` reaches the sandbox host but Python cannot resolve it.
- Added a first-pass multilingual normalization layer so existing create/update/delete workflows can reuse the same parser for simple prompts across the supported language set, including initial role and travel-expense phrase coverage.
- Tightened task classification to use word boundaries and expanded employee parsing to accept accented names such as `José Álvarez`.
- Added explicit `invoice_delete` classification as an unsupported path to avoid misrouting destructive invoice prompts into unrelated delete workflows.
- Added explicit unsupported task classification for `payment`, `credit note`, and `voucher` prompts to prevent false routing while those workflows remain unimplemented.
- Added explicit unsupported responses for `invoice_delete`, `payment`, `credit note`, and `voucher` prompts so the agent fails safely and descriptively while those workflows remain unimplemented.
- Product update now supports a deterministic `find product -> PUT /product/{id} -> verify description` flow.
- Product delete now supports a deterministic `find product -> DELETE /product/{id} -> verify absence` flow.
- Travel expense create now supports a deterministic `default employee -> POST /travelExpense -> verify title` flow.
- Customer create now supports a limited attachment-aware fallback that reads labeled `customer/name` and `email` lines from the first text-like attachment when inline prompt fields are missing.
- Travel expense create now supports a limited attachment-aware fallback that derives the title from the first attachment filename when the prompt only references an attached receipt/file.
- Travel expense update now supports a deterministic `default employee -> GET /travelExpense -> PUT /travelExpense/{id} -> verify title` flow.
- Travel expense delete now supports a deterministic `default employee -> GET /travelExpense -> DELETE /travelExpense/{id} -> verify absence` flow.

## Maintenance Rules
- Update `Current Capabilities` whenever a supported task type or handler changes.
- Update `Known Gaps` whenever a limitation is discovered, resolved, or reprioritized.
- Update request and response examples whenever `schemas.py` or endpoint behavior changes.
- Update `Operational Notes` whenever auth, startup, deployment, or security assumptions change.
- Add or amend `Decision Log` entries when an important implementation choice is made outside the code itself.
- Keep this file compact and factual; avoid speculative wording that makes planned features look implemented.
