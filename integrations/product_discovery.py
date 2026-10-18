"""Optional product adapters are composed outside the generic runtime."""

import os
from .ikea.source import IkeaSource
from ghostbuild_core.discovery.service import ProductDiscoveryService


def attach_discovery(runtime):
    enabled = (
        os.getenv(
            "GB_DISCOVERY",
            "1"
            if (runtime.asset_root / "knowledge/products/ikea/index.json").exists()
            else "0",
        )
        == "1"
    )
    if not enabled:
        return None
    path = runtime.sessions._path
    service = ProductDiscoveryService(
        runtime,
        [IkeaSource(runtime.asset_root)],
        path=path.with_name("discovery.json") if path else None,
        live=os.getenv("GB_DISCOVERY_LIVE", "1") == "1",
        # A confirmed product without a prepared guide compiles one from its official manual whenever paid live research
        # is on (GB_LIVE_RESEARCH=1, compile engine); GB_DISCOVERY_RESEARCH=0 opts out.
        research=os.getenv("GB_DISCOVERY_RESEARCH", os.getenv("GB_LIVE_RESEARCH", "0")) == "1",
    )

    # Old processes may have persisted an unidentified, generic product draft.
    # Keep its progress, but never resume that draft as the confirmed manual.
    active = runtime.playbook
    if active is not None and service.requires_identification(active.card):
        from contracts.models import GoalRequest
        runtime.resolve_goal(GoalRequest(session_id=runtime.session().id, mode="build", via="phone_text", text=active.card.title))
    return service
