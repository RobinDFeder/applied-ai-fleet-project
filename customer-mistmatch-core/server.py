"""
Customs Mismatch Resolver -- mock MCP server (POC)

Implements the tool set described in section 5 of the Fleet agent spec
("customs-mismatch-resolver-fleet-spec.md") against an in-memory mock
dataset, so the Fleet agent has real tools to call instead of just
reasoning in the abstract.

Run locally (stdio, for quick testing with an MCP inspector):
    python server.py

Run over HTTP for remote/Fleet access (what you actually deploy):
    python server.py --http
    # or set TRANSPORT=http as an env var, which is what the Procfile/
    # start command on Railway/Render should do.

Tools implemented (see data.py for the mock dataset + thresholds):
    list_held_shipments
    get_shipment_file
    get_flagged_document
    get_customs_ruleset
    check_mismatch_pattern
    draft_corrected_document
    validate_against_ruleset
    resubmit_to_customs        (mutates mock state -- treat as the
                                 "sensitive" tool Fleet should gate with
                                 Ask/approval)
    post_decision_receipt      (just logs/returns a formatted receipt)
    mark_hold_resolved         (mutates mock state -- also gate with
                                 Ask/approval)

None of this talks to a real customs authority or TMS. It exists so the
agent's Operating Behavior steps in AGENTS.md have something concrete to
call, and so a Fleet run produces a real trace instead of a hypothetical
one.
"""

import os
import copy
from datetime import datetime, timezone

from fastmcp import FastMCP

from data import (
    SHIPMENTS,
    RULESETS,
    KNOWN_SAFE_PATTERNS,
    AUTO_ACT_VALUE_THRESHOLD_EUR,
    AUTO_ACT_CONFIDENCE_BAR,
)

mcp = FastMCP(
    name="Customs Mismatch Resolver (Mock)",
    instructions=(
        "Mock tools for a customs document mismatch resolution POC. "
        "Data is entirely fictional, served in-memory, and resets on "
        "server restart. Use list_held_shipments to find work, then "
        "walk each shipment through the retrieve -> classify -> draft -> "
        "validate -> (auto-resubmit or escalate) sequence described in "
        "the agent's own instructions."
    ),
)

# Mutable copy so resubmit/mark_resolved calls can change state during a
# session without permanently editing the source data module.
_state = copy.deepcopy(SHIPMENTS)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@mcp.tool
def list_held_shipments() -> list[dict]:
    """
    Return every shipment currently held for a document mismatch.

    This is the entry point for a run: call this first to find out what,
    if anything, needs attention. Shipments with status != "held" (e.g.
    already cleared) are excluded.
    """
    return [
        {
            "shipment_id": s["shipment_id"],
            "destination_country": s["destination_country"],
            "declared_value_eur": s["declared_value_eur"],
            "held_reason": s["held_reason"],
        }
        for s in _state.values()
        if s["status"] == "held"
    ]


@mcp.tool
def get_shipment_file(shipment_id: str) -> dict:
    """
    Retrieve the full shipment record: value, jurisdiction, parties,
    carrier, and current status. Does not include the flagged document
    itself -- use get_flagged_document for that.
    """
    s = _state.get(shipment_id)
    if not s:
        return {"error": f"No shipment found with id {shipment_id!r}"}
    record = {k: v for k, v in s.items() if k != "flagged_document"}
    return record


@mcp.tool
def get_flagged_document(shipment_id: str) -> dict:
    """
    Retrieve the specific document that failed customs check for this
    shipment, including which field is at issue and why.
    """
    s = _state.get(shipment_id)
    if not s:
        return {"error": f"No shipment found with id {shipment_id!r}"}
    if not s.get("flagged_document"):
        return {"error": f"Shipment {shipment_id} has no flagged document (status: {s['status']})"}
    return s["flagged_document"]


@mcp.tool
def get_customs_ruleset(country: str, document_type: str, field: str) -> dict:
    """
    Retrieve the live customs ruleset explaining what a given document
    field is required to look like for a destination country. This is
    the "why is it actually failing" lookup -- call it after
    get_flagged_document to understand the specific rule in play.
    """
    key = (country, document_type, field)
    rule = RULESETS.get(key)
    if not rule:
        return {
            "error": (
                f"No ruleset entry found for country={country!r}, "
                f"document_type={document_type!r}, field={field!r}. "
                "Treat as an unfamiliar jurisdiction/rule -- do not "
                "auto-act on this."
            )
        }
    return {"country": country, "document_type": document_type, "field": field, **rule}


@mcp.tool
def check_mismatch_pattern(pattern_name: str) -> dict:
    """
    Classify a mismatch type against the known-safe pattern library.

    Pass a short pattern label describing the mismatch (e.g.
    "hs_code_digit_transposition", "unit_of_measure_format",
    "missing_optional_field"). Returns whether it's on the known-safe
    list that qualifies for auto-action consideration, or whether it
    must always be routed to a human regardless of value/confidence.
    """
    is_safe = pattern_name in KNOWN_SAFE_PATTERNS
    return {
        "pattern_name": pattern_name,
        "known_safe": is_safe,
        "known_safe_patterns": sorted(KNOWN_SAFE_PATTERNS),
        "note": (
            "On the known-safe list -- eligible for auto-act if value and "
            "confidence thresholds also pass."
            if is_safe
            else "NOT on the known-safe list -- must be routed to a human "
            "regardless of shipment value or confidence score."
        ),
    }


@mcp.tool
def draft_corrected_document(shipment_id: str, corrected_value: str, rationale: str) -> dict:
    """
    Produce a draft correction for the flagged field on a shipment's
    document. This does not submit anything -- it only records a
    proposed fix for validate_against_ruleset to check next.

    corrected_value: the proposed replacement value for the flagged field.
    rationale: a short explanation of why this correction is believed right.
    """
    s = _state.get(shipment_id)
    if not s or not s.get("flagged_document"):
        return {"error": f"No held shipment with a flagged document for id {shipment_id!r}"}
    draft = {
        "shipment_id": shipment_id,
        "document_id": s["flagged_document"]["document_id"],
        "field": s["flagged_document"]["field"],
        "original_value": s["flagged_document"]["declared_value"],
        "corrected_value": corrected_value,
        "rationale": rationale,
        "drafted_at": _now(),
    }
    s["_draft"] = draft
    return draft


@mcp.tool
def validate_against_ruleset(shipment_id: str) -> dict:
    """
    Grader step. Checks the most recent draft correction for a shipment
    (from draft_corrected_document) against the live ruleset and returns
    a pass/fail plus a confidence score.

    This is a mock validator: in this POC it approves any draft that
    differs from the original value and isn't empty, with a confidence
    score that's deliberately lower for jurisdictions/fields with no
    ruleset on file (mirrors "unfamiliar rule -> lower confidence").
    """
    s = _state.get(shipment_id)
    if not s:
        return {"error": f"No shipment found with id {shipment_id!r}"}
    draft = s.get("_draft")
    if not draft:
        return {"error": f"No draft correction found for {shipment_id} -- call draft_corrected_document first"}

    doc = s["flagged_document"]
    key = (s["destination_country"], doc["type"], doc["field"])
    has_ruleset = key in RULESETS

    passed = bool(draft["corrected_value"]) and draft["corrected_value"] != draft["original_value"]
    confidence = 0.95 if (passed and has_ruleset) else (0.55 if passed else 0.10)

    return {
        "shipment_id": shipment_id,
        "passed": passed,
        "confidence": confidence,
        "ruleset_on_file": has_ruleset,
        "notes": (
            "Draft checks out against a known ruleset."
            if (passed and has_ruleset)
            else "Draft is plausible but no matching ruleset was on file -- "
            "confidence deliberately capped below the auto-act bar."
            if passed
            else "Draft was empty or unchanged from the original -- validation failed."
        ),
    }


@mcp.tool
def resubmit_to_customs(shipment_id: str) -> dict:
    """
    Resubmit the corrected document to the customs authority for this
    shipment. This is a sensitive/mutating action -- in Fleet, this tool
    should be set to "Ask" so a human approves before it actually fires,
    except where your tiered-autonomy logic (value + known-safe pattern +
    confidence, all defined in AGENTS.md) says it's safe to proceed.

    Mutates mock state: marks the shipment as resubmitted.
    """
    s = _state.get(shipment_id)
    if not s:
        return {"error": f"No shipment found with id {shipment_id!r}"}
    if not s.get("_draft"):
        return {"error": f"No validated draft on file for {shipment_id} -- draft and validate first"}

    s["status"] = "resubmitted"
    return {
        "shipment_id": shipment_id,
        "action": "resubmitted",
        "corrected_value": s["_draft"]["corrected_value"],
        "resubmitted_at": _now(),
    }


@mcp.tool
def post_decision_receipt(
    shipment_id: str,
    tier: str,
    confidence: float,
    summary: str,
) -> dict:
    """
    Produce a decision receipt for an action taken on a shipment, in the
    format described in AGENTS.md: what was flagged, what changed,
    confidence, which tier it triggered, and a timestamp. In this mock
    server this just formats and returns the receipt (in a real
    deployment it would also post to Slack / a log store).

    tier: "auto" or "approval" -- which tier this decision fell into.
    """
    s = _state.get(shipment_id)
    if not s:
        return {"error": f"No shipment found with id {shipment_id!r}"}

    receipt = {
        "shipment_id": shipment_id,
        "destination_country": s["destination_country"],
        "declared_value_eur": s["declared_value_eur"],
        "auto_act_value_threshold_eur": AUTO_ACT_VALUE_THRESHOLD_EUR,
        "auto_act_confidence_bar": AUTO_ACT_CONFIDENCE_BAR,
        "tier": tier,
        "confidence": confidence,
        "summary": summary,
        "timestamp": _now(),
    }
    return receipt


@mcp.tool
def mark_hold_resolved(shipment_id: str) -> dict:
    """
    Mark a shipment's hold as resolved once customs has confirmed
    clearance. Sensitive/mutating action -- gate with "Ask" in Fleet.
    """
    s = _state.get(shipment_id)
    if not s:
        return {"error": f"No shipment found with id {shipment_id!r}"}
    s["status"] = "cleared"
    return {"shipment_id": shipment_id, "status": "cleared", "resolved_at": _now()}


@mcp.tool
def reset_mock_data() -> dict:
    """
    Reset the in-memory mock dataset back to its original state. Useful
    between demo runs so you can re-trigger the same test cases.
    """
    global _state
    _state = copy.deepcopy(SHIPMENTS)
    return {"status": "reset", "shipment_count": len(_state)}


if __name__ == "__main__":
    use_http = "--http" in os.sys.argv or os.environ.get("TRANSPORT", "").lower() == "http"
    if use_http:
        port = int(os.environ.get("PORT", 8000))
        mcp.run(transport="http", host="0.0.0.0", port=port)
    else:
        mcp.run()
