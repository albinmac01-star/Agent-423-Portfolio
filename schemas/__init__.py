"""
schemas/__init__.py — JSON schema validators.
Call validate_signal(), validate_ai_request(), etc. before processing any payload.
Raises jsonschema.ValidationError on invalid input.
"""
import json
import pathlib
import jsonschema

_SCHEMA_DIR = pathlib.Path(__file__).parent

def _load(name: str) -> dict:
    with open(_SCHEMA_DIR / name) as f:
        return json.load(f)

_SIGNAL_SCHEMA       = _load("signal_schema.json")
_AI_REQUEST_SCHEMA   = _load("ai_request.json")
_AI_RESPONSE_SCHEMA  = _load("ai_response.json")
_ESCALATION_SCHEMA   = _load("management_escalation.json")


def validate_signal(payload: dict) -> None:
    """Validate an incoming signal payload from the queue."""
    jsonschema.validate(instance=payload, schema=_SIGNAL_SCHEMA)


def validate_ai_request(payload: dict) -> None:
    """Validate the payload before sending to Claude."""
    jsonschema.validate(instance=payload, schema=_AI_REQUEST_SCHEMA)


def validate_ai_response(payload: dict) -> None:
    """Validate the JSON response returned by Claude."""
    jsonschema.validate(instance=payload, schema=_AI_RESPONSE_SCHEMA)


def validate_escalation(payload: dict) -> None:
    """Validate a management escalation payload before sending to Claude."""
    jsonschema.validate(instance=payload, schema=_ESCALATION_SCHEMA)
