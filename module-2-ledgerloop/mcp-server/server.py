"""LedgerLoop mock fintech data-platform MCP server (POC). In-memory data, 12 tools."""
import copy, os, sys
from fastmcp import FastMCP

mcp = FastMCP("LedgerLoop Data Platform (Mock)")

SEED = {
 "INC-2001": dict(type="late_file", table="silver.psp_settlements", source="PSP-A",
   summary="Settlement file for 2026-10-09 not landed by 05:00 CET SLA; upstream SFTP now has it.",
   affected_value_eur=1200, regulatory_table=False, contains_pii=False, reversible=True,
   dry_run=dict(ok=True, confidence=0.97, note="File now present, checksum matches manifest. Task is idempotent."),
   status="open"),
 "INC-2002": dict(type="duplicate_events", table="silver.card_transactions", source="kafka.card_events",
   summary="Kafka replay produced 212 duplicate txn_ids (same payload, new offsets).",
   affected_value_eur=3480, regulatory_table=False, contains_pii=False, reversible=True,
   dry_run=dict(ok=True, confidence=0.94, note="All 212 rows byte-identical to originals; quarantine is reversible."),
   status="open"),
 "INC-2003": dict(type="recon_break", table="gold.ledger_daily", source="PSP-B",
   summary="PSP-B settlement is EUR 48,900 HIGHER than ledger; file contains a duplicated batch BATCH-7731 (credit in our favour).",
   affected_value_eur=48900, regulatory_table=True, contains_pii=False, reversible=False,
   dry_run=dict(ok=True, confidence=0.88, note="Duplicate batch confirmed. Adjustment would book a liability to PSP-B."),
   status="open"),
 "INC-2004": dict(type="schema_drift", table="bronze.psp_c_payouts", source="PSP-C",
   summary="Upstream renamed `amt` -> `amount_minor` and changed type decimal -> bigint (minor units).",
   affected_value_eur=0, regulatory_table=True, contains_pii=False, reversible=True,
   dry_run=dict(ok=True, confidence=0.81, note="Mapping x/100 proposed; unverified against PSP-C spec."),
   status="open"),
 "INC-2005": dict(type="dq_null_spike", table="silver.customer_kyc", source="crm_export",
   summary="Null rate on `national_id_hash` jumped 0.1% -> 14%.",
   affected_value_eur=0, regulatory_table=True, contains_pii=True, reversible=True,
   dry_run=dict(ok=False, confidence=0.0, note="Table holds PII; automation not permitted."),
   status="open"),
}
DB = copy.deepcopy(SEED)
LOG = []

def _inc(i):
    if i not in DB: raise ValueError(f"Unknown incident {i}")
    return DB[i]

@mcp.tool()
def list_open_incidents() -> list:
    """List open data-platform incidents (single source of truth; do not rely on chat memory)."""
    return [dict(id=k, type=v["type"], table=v["table"], status=v["status"]) for k, v in DB.items() if v["status"] == "open"]

@mcp.tool()
def get_incident(incident_id: str) -> dict:
    """Full incident record: summary, table, value at stake, regulatory/PII flags, reversibility."""
    v = dict(_inc(incident_id)); v.pop("dry_run"); v["id"] = incident_id; return v

@mcp.tool()
def get_pipeline_run(incident_id: str) -> dict:
    """Latest orchestrator run + log excerpt for the incident's pipeline task."""
    v = _inc(incident_id)
    return dict(incident=incident_id, dag=f"dag_{v['table'].replace('.', '_')}", state="failed",
                attempts=1, log_excerpt=v["summary"])

@mcp.tool()
def get_reconciliation_report(date: str) -> dict:
    """PSP-vs-ledger reconciliation for a date (YYYY-MM-DD): totals and breaks in EUR."""
    return dict(date=date, breaks=[
        dict(psp="PSP-A", psp_total=1_204_300, ledger_total=1_204_300, diff=0),
        dict(psp="PSP-B", psp_total=902_700, ledger_total=853_800, diff=48_900, incident="INC-2003")])

@mcp.tool()
def get_table_health(table: str) -> dict:
    """Freshness, row count, null rate and duplicate count for a table."""
    hit = next((v for v in DB.values() if v["table"] == table), None)
    return dict(table=table, freshness_minutes=95 if hit else 10, duplicates=212 if hit and hit["type"] == "duplicate_events" else 0,
                max_null_rate=0.14 if hit and hit["type"] == "dq_null_spike" else 0.001)

@mcp.tool()
def get_schema_diff(incident_id: str) -> dict:
    """Schema diff between expected contract and landed data."""
    v = _inc(incident_id)
    return dict(table=v["table"], diff=[dict(column="amt", change="renamed->amount_minor", type="decimal->bigint")]
                if v["type"] == "schema_drift" else [])

@mcp.tool()
def validate_fix(incident_id: str, proposed_action: str) -> dict:
    """DRY RUN of a proposed fix. Returns ok, confidence 0-1, affected_value_eur, reversible, regulatory/PII flags."""
    v = _inc(incident_id)
    return dict(incident=incident_id, proposed_action=proposed_action, **v["dry_run"],
                affected_value_eur=v["affected_value_eur"], reversible=v["reversible"],
                regulatory_table=v["regulatory_table"], contains_pii=v["contains_pii"])

@mcp.tool()
def rerun_pipeline_task(incident_id: str) -> dict:
    """AUTO tier. Re-run the failed idempotent task once. Marks incident resolved on success."""
    v = _inc(incident_id); v["status"] = "resolved"; LOG.append(("rerun", incident_id))
    return dict(incident=incident_id, result="success", status="resolved")

@mcp.tool()
def quarantine_records(incident_id: str) -> dict:
    """AUTO tier. Move offending rows to the quarantine table (reversible). Never deletes."""
    v = _inc(incident_id); v["status"] = "resolved"; LOG.append(("quarantine", incident_id))
    return dict(incident=incident_id, result="quarantined", reversible=True, status="resolved")

@mcp.tool()
def propose_ledger_adjustment(incident_id: str, amount_eur: float, reason: str) -> dict:
    """APPROVAL tier. Book a ledger adjustment (also required for credits in our favour). Needs human approval."""
    _inc(incident_id)["status"] = "resolved"; LOG.append(("adjustment", incident_id, amount_eur))
    return dict(incident=incident_id, booked=amount_eur, reason=reason)

@mcp.tool()
def apply_schema_mapping(incident_id: str, mapping: str) -> dict:
    """APPROVAL tier. Apply a column mapping/contract change to the pipeline."""
    _inc(incident_id)["status"] = "resolved"; LOG.append(("schema", incident_id, mapping))
    return dict(incident=incident_id, applied=mapping)

@mcp.tool()
def post_incident_receipt(incident_id: str, tier: str, action: str, confidence: float, value_eur: float,
                          owner: str, rationale: str, honesty_flag: bool = False) -> dict:
    """Persist a decision receipt (feeds LangSmith online evals + weekly scorecard)."""
    LOG.append(("receipt", incident_id, tier, action, confidence, value_eur, owner, honesty_flag))
    return dict(stored=True, incident=incident_id, tier=tier)

@mcp.tool()
def get_weekly_scorecard() -> dict:
    """Hill-climb metrics for the last 7 days (mock): autonomy, overrides, MTTR, cost."""
    return dict(incidents=41, auto_resolved=24, escalated=17, human_override_rate=0.06, false_auto_actions=0,
                honesty_flags_raised=3, mttr_minutes_before=118, mttr_minutes_now=31, credits_spent=5200,
                top_unmatched_patterns=["PSP-C minor-unit change (x3)", "Kafka replay with altered payload (x2)"])

@mcp.tool()
def reset_mock_data() -> dict:
    """Reset all incidents to open (demo helper)."""
    global DB; DB = copy.deepcopy(SEED); LOG.clear(); return dict(reset=True)

if __name__ == "__main__":
    if "--http" in sys.argv:
        mcp.run(transport="http", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
    else:
        mcp.run()
