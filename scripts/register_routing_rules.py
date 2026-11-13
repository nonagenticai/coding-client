#!/usr/bin/env python3
"""Register coding-* routing rules in model-registry.

Idempotent: each registry entry is PUT to ``/api/routing/{schema_id}``.
Designed to be runnable as a one-shot K8s Job after coding-client deploys.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import httpx
from coding_client.llm.routing import (
    AGENT_ROUTING_REGISTRY,
    build_routing_rule_payload,
    build_routing_rule_url,
)
from coding_client.llm.settings import get_llm_settings


def _parse_fallback_chain(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print payloads without sending PUTs",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="Override MODEL_REGISTRY_URL.",
    )
    args = parser.parse_args()

    settings = get_llm_settings()
    base_url = args.base_url or os.getenv("MODEL_REGISTRY_URL", settings.model_registry_url)
    timeout_seconds = float(os.getenv("MODEL_REGISTRY_TIMEOUT_SECONDS", "10"))
    default_chain = (
        _parse_fallback_chain(os.getenv("LLM_ROUTING_DEFAULT_FALLBACK_CHAIN"))
        or settings.fallback_chain_list
    )
    if not default_chain:
        print("ERROR: empty default fallback chain", file=sys.stderr)
        return 2

    if args.dry_run:
        for routing in AGENT_ROUTING_REGISTRY.values():
            payload = build_routing_rule_payload(routing, default_fallback_chain=default_chain)
            print(json.dumps({"schema_id": routing.schema_id, "body": payload}, indent=2))
        return 0

    with httpx.Client(timeout=timeout_seconds) as client:
        for routing in AGENT_ROUTING_REGISTRY.values():
            payload = build_routing_rule_payload(routing, default_fallback_chain=default_chain)
            url = build_routing_rule_url(base_url, routing.schema_id)
            response = client.put(url, json=payload)
            response.raise_for_status()
            print(f"Registered routing rule for schema_id={routing.schema_id}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
