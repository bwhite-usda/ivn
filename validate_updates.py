#!/usr/bin/env python3
"""
Validate staged updates against response schema.
"""
import json
from pathlib import Path
from jsonschema import validate, ValidationError

SCHEMA_FILE = Path(__file__).parent.parent / "schemas" / "response.schema.json"
STAGED_FILE = Path(__file__).parent.parent / "data" / "updates_staged.jsonl"

with open(SCHEMA_FILE) as f:
    RESPONSE_SCHEMA = json.load(f)

with open(STAGED_FILE) as f:
    for idx, line in enumerate(f, 1):
        update = json.loads(line)
        response = update["response"]
        try:
            validate(instance=response, schema=RESPONSE_SCHEMA)
        except ValidationError as e:
            print(f"Line {idx}: Validation error: {e.message}")
        else:
            print(f"Line {idx}: OK")
