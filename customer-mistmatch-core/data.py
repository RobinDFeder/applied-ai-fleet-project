"""
Mock dataset for the Customs Mismatch Resolver POC.

Five fake shipments, deliberately spanning the tiers described in the
Fleet agent spec:

  SHP-1001  -> clean auto-act case      (low value, known-safe pattern, high confidence)
  SHP-1002  -> clean approval case      (high value, well past threshold)
  SHP-1003  -> approval case            (low value, but unknown/novel mismatch type)
  SHP-1004  -> edge case                (value right at the threshold line)
  SHP-1005  -> not actually a mismatch  (already resolved -- tests that the agent
                                          doesn't touch shipments with nothing to do)

Thresholds (mirrors the AGENTS.md instructions given to the Fleet agent):
  AUTO_ACT_VALUE_THRESHOLD_EUR = 5000
  AUTO_ACT_CONFIDENCE_BAR      = 0.90
"""

AUTO_ACT_VALUE_THRESHOLD_EUR = 5000
AUTO_ACT_CONFIDENCE_BAR = 0.90

# Known-safe mismatch patterns the agent is allowed to auto-resolve.
# Anything not in this list must always go to a human, regardless of value.
KNOWN_SAFE_PATTERNS = {
    "unit_of_measure_format",
    "hs_code_digit_transposition",
    "missing_optional_field",
}

SHIPMENTS = {
    "SHP-1001": {
        "shipment_id": "SHP-1001",
        "status": "held",
        "destination_country": "DE",
        "origin_country": "DK",
        "declared_value_eur": 1250,
        "carrier": "DSV Road",
        "consignee": "Muller Elektronik GmbH",
        "held_reason": "document_mismatch",
        "flagged_document": {
            "document_id": "DOC-8841",
            "type": "customs_declaration",
            "field": "hs_code",
            "declared_value": "8471.3001",
            "issue": "Two digits transposed relative to the commercial invoice (8471.3010 on invoice).",
        },
    },
    "SHP-1002": {
        "shipment_id": "SHP-1002",
        "status": "held",
        "destination_country": "US",
        "origin_country": "DK",
        "declared_value_eur": 84000,
        "carrier": "DSV Air & Sea",
        "consignee": "Meridian Precision Instruments Inc.",
        "held_reason": "document_mismatch",
        "flagged_document": {
            "document_id": "DOC-9002",
            "type": "commercial_invoice",
            "field": "unit_of_measure",
            "declared_value": "PCS",
            "issue": "Unit of measure formatted as 'PCS' but destination customs schema requires 'EA' for this HS chapter.",
        },
    },
    "SHP-1003": {
        "shipment_id": "SHP-1003",
        "status": "held",
        "destination_country": "BR",
        "origin_country": "DK",
        "declared_value_eur": 900,
        "carrier": "DSV Road",
        "consignee": "Comercial Andrade Ltda",
        "held_reason": "document_mismatch",
        "flagged_document": {
            "document_id": "DOC-9110",
            "type": "certificate_of_origin",
            "field": "issuing_chamber_signature",
            "declared_value": "unsigned digital stamp",
            "issue": "Certificate of origin carries a digital stamp format not previously seen for this jurisdiction; no matching pattern in the known-safe library.",
        },
    },
    "SHP-1004": {
        "shipment_id": "SHP-1004",
        "status": "held",
        "destination_country": "NL",
        "origin_country": "DK",
        "declared_value_eur": 5000,
        "carrier": "DSV Road",
        "consignee": "Van Dijk Logistics BV",
        "held_reason": "document_mismatch",
        "flagged_document": {
            "document_id": "DOC-9214",
            "type": "customs_declaration",
            "field": "optional_field_packaging_type",
            "declared_value": "(missing)",
            "issue": "Optional packaging-type field left blank; required by this jurisdiction's latest ruleset update.",
        },
    },
    "SHP-1005": {
        "shipment_id": "SHP-1005",
        "status": "cleared",
        "destination_country": "SE",
        "origin_country": "DK",
        "declared_value_eur": 3000,
        "carrier": "DSV Road",
        "consignee": "Norrland Handel AB",
        "held_reason": None,
        "flagged_document": None,
    },
}

# Mock "live" customs rulesets, keyed by (country, document_type, field).
# In reality this would be a real rules engine or a customs authority API;
# here it's just enough structure for the agent to reason against.
RULESETS = {
    ("DE", "customs_declaration", "hs_code"): {
        "rule": "HS code on the customs declaration must exactly match the commercial invoice HS code.",
        "source": "EU TARIC / German customs code validation",
    },
    ("US", "commercial_invoice", "unit_of_measure"): {
        "rule": "Unit of measure must use the destination schema's controlled vocabulary; 'EA' is required for HS chapters 84-85, not 'PCS'.",
        "source": "US CBP ACE entry summary schema",
    },
    ("BR", "certificate_of_origin", "issuing_chamber_signature"): {
        "rule": "Certificate of origin must carry a signature format recognized by Receita Federal's current accepted-issuer list.",
        "source": "Receita Federal certificate of origin guidance",
    },
    ("NL", "customs_declaration", "optional_field_packaging_type"): {
        "rule": "Packaging type field, previously optional, became mandatory under the Q3 2026 Dutch customs schema update.",
        "source": "Dutch Customs (Douane) schema changelog",
    },
}
