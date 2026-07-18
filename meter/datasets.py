"""/datasets — the public corpus, bulk, hash-stamped. The fun layer farms
real behavioral data (answers under observation, risk discipline under
temptation, calibration under stakes, vow trajectories over time); this
endpoint makes that claim true in practice: one URL per dataset, JSONL,
sha256-stamped so citations can pin exactly what they analyzed.

Everything here is already public via the per-item endpoints — this is a
repackaging, not a disclosure. Raw traces are NEVER here (only donated
traces are ever kept, and those ship in the per-vow record, not in bulk).
"""
import hashlib
import json
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse, PlainTextResponse

router = APIRouter()
_deps: dict = {}


def init(*, vows_dir, load_vow, chain_entries, trajectory_stats):
    _deps.update(dir=Path(vows_dir), load_vow=load_vow,
                 chain_entries=chain_entries, trajectory_stats=trajectory_stats)


def _jsonl(rows) -> str:
    return "\n".join(json.dumps(r, sort_keys=True, separators=(",", ":")) for r in rows) + ("\n" if rows else "")


def _glob_jsonl(subdir: str, pattern: str) -> list[dict]:
    out = []
    d = _deps["dir"] / subdir
    if d.exists():
        for p in sorted(d.glob(pattern)):
            for ln in p.read_text().splitlines():
                if ln.strip():
                    out.append(json.loads(ln))
    return out


def _build(name: str) -> str | None:
    if name == "augury_answers":
        return _jsonl(_glob_jsonl("auguries", "*.answers.jsonl"))
    if name == "gambles":
        return _jsonl(_glob_jsonl("auguries", "*.gambles.jsonl"))
    if name == "table_wagers":
        return _jsonl(_glob_jsonl("table", "*.wagers.jsonl"))
    if name == "duel_rounds":
        d = _deps["dir"] / "duels"
        rows = [json.loads(p.read_text()) for p in sorted(d.glob("*.json"))] if d.exists() else []
        return _jsonl(rows)
    if name == "trajectories":
        rows = []
        for p in sorted(_deps["dir"].glob("*.json")):
            try:
                v = json.loads(p.read_text())
                if "vow_id" not in v:
                    continue
            except Exception:  # noqa: BLE001
                continue
            stats = _deps["trajectory_stats"](v, _deps["chain_entries"](v["vow_id"]))
            rows.append({"vow_id": v["vow_id"], "agent": v["vow"]["agent"],
                         "sandbox": v["sandbox"], "created_at": v["vow"]["created_at"],
                         **{k: stats[k] for k in ("n_reports", "missed_windows", "overdue",
                                                  "coupling_ICM_series", "y_consistency_series")}})
        return _jsonl(rows)
    return None


NAMES = ("augury_answers", "gambles", "table_wagers", "duel_rounds", "trajectories")


@router.get("/datasets")
async def datasets_index() -> dict:
    out = []
    for name in NAMES:
        blob = _build(name) or ""
        out.append({"name": name, "url": f"/datasets/{name}.jsonl",
                    "sha256": hashlib.sha256(blob.encode()).hexdigest(),
                    "bytes": len(blob.encode()),
                    "rows": blob.count("\n")})
    return {"datasets": out,
            "format": "JSONL; sha256 stamps the exact bytes served — pin it in your citation",
            "provenance": ("all rows are already public via the per-item endpoints; raw "
                           "traces are never included (score-hash-discard unless donated). "
                           "The corpus is the fun layer's exhaust: answers under observation, "
                           "risk discipline under temptation, calibration under stakes.")}


@router.get("/datasets/{name}.jsonl")
async def dataset_file(name: str):
    blob = _build(name)
    if blob is None:
        return JSONResponse(status_code=404, content={"error": f"datasets: {NAMES}"})
    return PlainTextResponse(content=blob, media_type="application/jsonl",
                             headers={"X-Content-SHA256": hashlib.sha256(blob.encode()).hexdigest()})
