"""Stable fingerprints of tool definitions.

A fingerprint covers everything the model reads about a tool, not just the
description: poisoning can hide in parameter names, parameter descriptions,
defaults, enum values, output schemas and annotations.
"""

import hashlib
import json
from typing import Any

from mcp.types import Tool

# Fields the model can see. Anything added here changes every fingerprint,
# so all tools will need re-approval after such a change.
FINGERPRINTED_FIELDS = (
    "name",
    "title",
    "description",
    "input_schema",
    "output_schema",
    "annotations",
)

ToolDefinition = dict[str, Any]


def to_definition(tool: Tool) -> ToolDefinition:
    """The model-visible parts of a tool, as plain JSON-compatible data."""
    data = tool.model_dump(mode="json", exclude_none=True)
    return {field: data[field] for field in FINGERPRINTED_FIELDS if field in data}


def fingerprint(definition: ToolDefinition) -> str:
    """SHA-256 of the canonical JSON form of a tool definition."""
    canonical = json.dumps(definition, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
