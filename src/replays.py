"""
"Watch the AI read": the recorded photo readings from the accuracy test, replayed field by field.

Which packs to show and the card for each live here, so the static site (build_static.py) and the
Streamlit app (app.py) replay exactly the same readings.
"""

from __future__ import annotations

import json
from pathlib import Path

from src import ui
from src.rules.decoder import decode_label

ROOT = Path(__file__).resolve().parent.parent
PREDS = ROOT / "eval" / "results" / "extraction_claude-subagents.jsonl"   # the AI's recorded photo readings

# (barcode, chip label, chip is a miss?, summary override)
REPLAYS = [
    ("8901719125478", "clean photos", False, None),
    ("8904004400212", "clean photos", False, None),
    ("8908001588560", "AI vs database", True,
     "The AI matched the database on only <b>2 of 8</b> numbers. Look at the nutrition photo: energy 317.6, fat 8.82, "
     "sodium 250. <b>The AI read the pack correctly; the crowd database is wrong.</b> Some of the 13% “errors” in the "
     "accuracy score are the database’s mistakes, not the AI’s."),
    ("8901725005214", "blurry photo", True,
     "One number differs: protein, <b>8.7 read vs 9.7 in the database</b>. The photo is too blurry to say who is right, "
     "and the AI said so itself in its note. On hard-to-read photos accuracy drops to 66%, which is why the app warns you."),
]


def replay_cards(rows: dict) -> list[tuple[str, str, str, bool, str]]:
    """(barcode, pack name, chip label, miss?, html) for every recorded reading that this copy has the data for.

    rows: barcode -> {"label": ..., "image_urls": {...}} from the test set. The html is the photos, the field-by-field
    check against the database, then the verdict worked out from the AI's own reading.
    """
    if not PREDS.exists():
        return []
    preds = {}
    for line in PREDS.open(encoding="utf-8"):
        r = json.loads(line)
        preds[r["barcode"]] = r["pred"]
    out = []
    for code, tag, miss, summary in REPLAYS:
        if code not in rows or code not in preds:
            continue
        ref, pred = rows[code]["label"], dict(preds[code])
        imgs = rows[code].get("image_urls") or {}
        name = ui.full_name(ref.get("brand"), ref.get("product_name"))
        pred["barcode"] = code
        result = decode_label(pred)
        lights = ui._lights(pred.get("per_100") or {}, result["product"]["is_liquid"])
        card = ui.replay_card(name, imgs, ui.read_check(pred, ref), pred, summary)
        html = (card + ui.top_card(pred, result, imgs.get("front"), lights) + ui.health_card(result)
                + ui.three_things(result, lights)
                + ui.sugar_cards(result))
        out.append((code, name, tag, miss, html))
    return out
