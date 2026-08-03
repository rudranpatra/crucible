"""
Threat Dragon Importer
Converts an OWASP Threat Dragon JSON export into Crucible's normalized
Threat schema. This is the only importer Phase A ships — no Mermaid, no
Draw.io, no Microsoft TMT. One input, by design.

Supported shapes (Threat Dragon has changed its export format across
versions, so this is deliberately tolerant):

  v2.x  {"detail": {"diagrams": [{"cells": [{"data": {"threats": [...]}}]}]}}
  v1.x  {"detail": {"diagrams": [{"diagram": {"cells": [{"threats": [...]}]}}]}}
  flat  {"threats": [...]}                                   (any other tool)

By default, only threats whose source status is "Open" (or unset) are
imported — "Mitigated" / "NotApplicable" threats don't need re-validation.
"""

import json
from pathlib import Path
from typing import Any, Dict, List

from threats.schema import Threat

_SKIPPED_STATUSES = {"mitigated", "notapplicable", "not applicable"}


class ThreatDragonImporter:
    """Normalizes a Threat Dragon JSON model into a list of Threat objects."""

    def import_file(self, path: str, include_mitigated: bool = False) -> List[Threat]:
        raw_text = Path(path).read_text()
        try:
            model = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path} is not valid JSON: {exc}") from exc
        return self.import_dict(model, include_mitigated=include_mitigated)

    def import_dict(self, model: Dict[str, Any], include_mitigated: bool = False) -> List[Threat]:
        threats: List[Threat] = []
        seen_ids: set = set()

        for diagram in self._diagrams(model):
            diagram_title = diagram.get("title", "diagram")
            diagram_framework = diagram.get("diagramType", "STRIDE")

            for cell in diagram.get("cells", []):
                data = cell.get("data", cell)
                component = data.get("name") or cell.get("shape", "component")

                for raw_threat in data.get("threats", []):
                    threat = self._normalize(
                        raw_threat,
                        framework=diagram_framework,
                        component=component,
                        diagram_title=diagram_title,
                    )
                    if threat is None:
                        continue
                    if not include_mitigated and self._is_skipped(raw_threat):
                        continue
                    if threat.id in seen_ids:
                        threat.id = f"{threat.id}-{len(threats)}"
                    seen_ids.add(threat.id)
                    threats.append(threat)

        # Flat/root-level threats — supports tools that don't nest under diagrams.
        for raw_threat in model.get("threats", []):
            threat = self._normalize(raw_threat, framework="STRIDE", component="unassigned")
            if threat is None:
                continue
            if not include_mitigated and self._is_skipped(raw_threat):
                continue
            if threat.id in seen_ids:
                threat.id = f"{threat.id}-{len(threats)}"
            seen_ids.add(threat.id)
            threats.append(threat)

        return threats

    # ── internals ─────────────────────────────────────────────────────────────

    def _diagrams(self, model: Dict[str, Any]) -> List[Dict[str, Any]]:
        detail = model.get("detail", model)
        diagrams = detail.get("diagrams", [])
        # v1 nests cells one level deeper under "diagram"
        normalized = []
        for d in diagrams:
            normalized.append(d.get("diagram", d))
        return normalized

    def _is_skipped(self, raw_threat: Dict[str, Any]) -> bool:
        status = str(raw_threat.get("status", "")).strip().lower()
        return status in _SKIPPED_STATUSES

    def _normalize(
        self,
        raw: Dict[str, Any],
        framework: str,
        component: str,
        diagram_title: str = "",
    ) -> Threat:
        if not raw.get("title") and not raw.get("description"):
            return None

        threat_id = str(raw.get("id") or self._fallback_id(raw))
        severity = str(raw.get("severity") or "medium").strip().lower()
        if severity not in {"critical", "high", "medium", "low"}:
            severity = "medium"

        return Threat(
            id=threat_id,
            title=raw.get("title") or raw.get("description", "")[:80],
            description=raw.get("description", ""),
            framework=framework,
            technique=str(raw.get("type", "")).strip(),
            severity=severity,
            component=component,
            source={
                "diagram": diagram_title,
                "status": raw.get("status", ""),
                "mitigation": raw.get("mitigation", ""),
                "number": raw.get("number"),
            },
        )

    def _fallback_id(self, raw: Dict[str, Any]) -> str:
        title = raw.get("title") or raw.get("description") or "threat"
        slug = "".join(c if c.isalnum() else "-" for c in title.lower()).strip("-")
        return f"td-{slug[:40]}"
