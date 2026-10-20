#!/usr/bin/env python3
"""Read-only design checks. No dependencies, approval inference, or content scoring."""
import argparse
import json
from pathlib import Path


def check(plan, base):
    errors, pending = [], []
    if not isinstance(plan, dict):
        return {"ok": False, "errors": ["Plan must be an object"], "pending": []}
    for key in ("title", "audience", "performance_task"):
        if not isinstance(plan.get(key), str) or not plan[key].strip():
            errors.append(f"Missing {key}")
    if plan.get("schema_version") not in (1, 2):
        errors.append("Unsupported schema_version")
    if plan.get("stage") not in (("outline", "script") if plan.get("schema_version") == 2 else ("outline", "courseware")):
        errors.append("Invalid stage")

    groups = {}
    for key in ("sources", "objectives", "units", "assessments", "decisions", "issues"):
        rows = plan.get(key)
        if not isinstance(rows, list):
            errors.append(f"{key} must be an array")
            rows = []
        mapped = {}
        for i, row in enumerate(rows):
            if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"].strip():
                errors.append(f"{key}[{i}] needs an id")
                continue
            if row["id"] in mapped:
                errors.append(f"Duplicate {key} id: {row['id']}")
            mapped[row["id"]] = row
        groups[key] = mapped
    for key in ("sources", "objectives", "units", "assessments"):
        if not groups[key]:
            errors.append(f"No {key}")

    def require(row, keys):
        for key in keys:
            if not isinstance(row.get(key), str) or not row[key].strip():
                errors.append(f"{row['id']}: missing {key}")

    def refs(row):
        links = row.get("source_refs")
        if not isinstance(links, list) or not links:
            errors.append(f"{row['id']}: needs source_refs")
            return
        for ref in links:
            if not isinstance(ref, dict) or not isinstance(ref.get("source_id"), str) or ref["source_id"] not in groups["sources"] or not isinstance(ref.get("locator"), str) or not ref["locator"].strip():
                errors.append(f"{row['id']}: invalid source reference")

    assessed, taught = set(), set()
    def objectives(row):
        ids = row.get("objective_ids")
        if not isinstance(ids, list) or not ids:
            errors.append(f"{row['id']}: needs objective_ids")
            return set()
        valid = set()
        for oid in ids:
            if not isinstance(oid, str) or oid not in groups["objectives"]:
                errors.append(f"{row['id']}: unknown objective {oid}")
            else:
                valid.add(oid)
        return valid

    for row in groups["sources"].values():
        require(row, ("title", "location", "kind"))
        if row.get("kind") == "file" and isinstance(row.get("location"), str):
            target = Path(row.get("location", ""))
            if not target.is_absolute():
                target = base / target
            if not target.is_file():
                errors.append(f"{row['id']}: source file missing")
    for row in groups["objectives"].values():
        require(row, ("statement", "evidence", "criterion"))
    for row in groups["units"].values():
        require(row, ("title", "media", "media_reason", "activity"))
        if plan.get("schema_version") == 2 and row.get("disposition") in ("core", "optional"):
            require(row, ("teaching_method", "teaching_reason"))
        if row.get("disposition") not in ("core", "optional", "job_aid", "separate", "omit"):
            errors.append(f"{row['id']}: invalid disposition")
        refs(row)
        if row.get("disposition") in ("core", "optional"):
            taught.update(objectives(row))
    for row in groups["assessments"].values():
        require(row, ("task", "criteria", "feedback"))
        assessed.update(objectives(row))
    for oid in groups["objectives"]:
        if oid not in taught:
            errors.append(f"{oid}: no teaching unit")
        if oid not in assessed:
            errors.append(f"{oid}: no assessment")

    for row in groups["decisions"].values():
        require(row, ("question", "finding"))
        opts = row.get("options", [])
        if not isinstance(opts, list):
            opts = []
        option_ids = [x.get("id") for x in opts if isinstance(x, dict)]
        if len(opts) < 2 or len(option_ids) != len(opts) or any(not isinstance(i, str) or not i for i in option_ids) or len(set(option_ids)) != len(option_ids):
            errors.append(f"{row['id']}: invalid options")
        for opt in opts:
            if isinstance(opt, dict) and (not opt.get("label") or not opt.get("impact")):
                errors.append(f"{row['id']}: option needs label and impact")
        if row.get("recommended") not in option_ids:
            errors.append(f"{row['id']}: invalid recommendation")
        state = row.get("status")
        blocks = row.get("blocking_for")
        if not isinstance(blocks, list) or any(x not in ("courseware", "production") for x in blocks):
            errors.append(f"{row['id']}: invalid blocking_for")
            blocks = []
        if state == "open":
            if row.get("selected") is not None:
                errors.append(f"{row['id']}: open decision cannot have a selection")
            pending.append({"id": row["id"], "kind": "decision", "blocks": blocks})
        elif state in ("confirmed", "delegated"):
            if row.get("selected") not in option_ids or not row.get("evidence"):
                errors.append(f"{row['id']}: resolved decision needs selection and evidence")
        else:
            errors.append(f"{row['id']}: invalid decision status")
    for row in groups["issues"].values():
        require(row, ("detail",))
        state, block = row.get("state"), row.get("blocks")
        if state not in ("open", "resolved", "mitigated") or block not in ("none", "courseware", "production"):
            errors.append(f"{row['id']}: invalid issue state/blocks")
        elif state == "open":
            pending.append({"id": row["id"], "kind": "issue", "blocks": [] if block == "none" else [block]})
        elif not row.get("resolution"):
            errors.append(f"{row['id']}: resolved/mitigated issue needs resolution")
        if row.get("source_refs"):
            refs(row)

    handoff = plan.get("handoff")
    if not isinstance(handoff, dict):
        handoff = {}
        errors.append("Missing handoff")
    for flag in ("ready_for_courseware", "ready_for_production"):
        if not isinstance(handoff.get(flag), bool):
            errors.append(f"{flag} must be a boolean")
    blocked = {b for item in pending for b in item["blocks"]}
    if handoff.get("ready_for_courseware") and "courseware" in blocked:
        errors.append("Courseware readiness conflicts with unresolved decisions/issues")
    if handoff.get("ready_for_production"):
        if blocked:
            errors.append("Production readiness conflicts with unresolved decisions/issues")
        modern = plan.get("schema_version") == 2
        file = plan.get("script_file" if modern else "courseware_file")
        if plan.get("stage") != ("script" if modern else "courseware") or not isinstance(file, str) or not file.strip() or not (base / file).is_file():
            errors.append("Production readiness requires an existing confirmed-script candidate" if modern else "Production readiness requires a courseware stage and existing draft")
    return {"ok": not errors, "errors": errors, "pending": pending,
            "counts": {k: len(v) for k, v in groups.items()},
            "scope": "Structure and links only; no proof of approval, facts, or learning effectiveness"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    args = parser.parse_args()
    try:
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
        report = check(plan, args.plan.resolve().parent)
    except (OSError, ValueError) as exc:
        report = {"ok": False, "errors": [str(exc)], "pending": []}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
