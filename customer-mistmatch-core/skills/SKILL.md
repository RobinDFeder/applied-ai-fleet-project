---
name: mismatch-pattern-library
description: Reference for classifying customs document mismatches as known-safe (eligible for auto-action consideration) or requiring human review regardless of shipment value or confidence.
---

# Mismatch Pattern Library

Use this skill whenever `check_mismatch_pattern` is called or whenever you
need to decide whether a mismatch type qualifies for the auto-act tier.
This library is deliberately short — a small, well-understood allowlist —
because the cost of an incorrect auto-resubmission (a shipment re-held, a
customs penalty, an audit finding) is far higher than the cost of an
unnecessary human review.

## Known-safe patterns (eligible for auto-act, subject to value and
confidence thresholds in AGENTS.md)

- **hs_code_digit_transposition** — Two digits in the HS code are
  transposed relative to the commercial invoice, and the invoice's HS code
  is itself well-formed. Correction: replace with the invoice's HS code.
- **unit_of_measure_format** — Unit of measure uses an unrecognized string
  (e.g. "PCS") where the destination schema expects a specific controlled
  vocabulary value (e.g. "EA"). Correction: substitute the destination
  schema's required unit string; do not change the underlying quantity.
- **missing_optional_field** — A field that was formerly optional but has
  become mandatory under a schema update, and the correct value is
  unambiguously derivable from other fields already on the shipment record
  (e.g. packaging type inferred from a matching field elsewhere in the
  document set). Correction: populate the field; do not fabricate a value
  that isn't derivable from existing data.

## Always requires human review (never auto-act, regardless of value)

- Any mismatch type not explicitly listed above.
- Signature, stamp, or certification format issues (e.g. an unrecognized
  digital signature format on a certificate of origin) — these often
  reflect a genuine authenticity question, not a formatting error, and
  should never be resolved without a human judgment call.
- Consignee or party name mismatches — these can indicate a genuine routing
  or fraud issue, not a typo.
- Anything where `get_customs_ruleset` returns no matching rule for the
  jurisdiction/document type/field combination — an unfamiliar rule means
  there is no verified basis for a confident correction.
- Anything where `validate_against_ruleset` confidence is below 90%,
  regardless of pattern match.

## Why the list stays short

Widening this list is a deliberate decision, not a default. Per Anthropic's
guidance on building trust with agents over time, autonomy should expand in
proportion to demonstrated reliability — a pattern earns a place on this
list only after repeated, correction-free auto-resolutions, reviewed by a
human. Do not add a new pattern to this list on your own reasoning alone;
recommend it to a human maintainer instead, with the supporting evidence
from your run history.
