"""
Build the labelled test set from Open Food Facts (India subset).

    python eval/build_testset.py            # 100 products with nutrition + ingredient photos
    python eval/build_testset.py --n 200

For every product we keep:
  - the OFF structured data (nutriments, ingredient text, serving)  -> "reference" labels
  - the pack photos (front, ingredients, nutrition)                 -> inputs for the vision model
  - a sanity verdict: OFF rows that fail sanity() are kept but marked, so they can be hand-corrected
    in eval/manual_labels.csv instead of scored as truth.

Writes eval/data/testset.jsonl and eval/data/images/<barcode>_<kind>.jpg
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.off_api import UA, drop_implausible, fetch_product, sanity, search_codes_india, to_label  # noqa: E402
from src.rules.decoder import split_ingredients  # noqa: E402

DATA = ROOT / "eval" / "data"
IMG = DATA / "images"


def download(url: str, dest: Path) -> bool:
    if dest.exists():
        return True
    try:
        r = requests.get(url, headers=UA, timeout=60)
        if r.status_code == 200 and r.content:
            dest.write_bytes(r.content)
            return True
    except requests.RequestException:
        pass
    return False


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--pages", type=int, default=12, help="max OFF search pages to scan")
    args = ap.parse_args()
    IMG.mkdir(parents=True, exist_ok=True)

    rows, seen = [], set()
    page = 0
    while page < args.pages:
        page += 1
        codes = []
        for attempt in range(4):
            try:
                codes, total = search_codes_india(page=page, page_size=100)
                if page == 1:
                    print(f"{total} India products with completed nutrition + ingredients on OFF")
                break
            except requests.RequestException as e:
                wait = 15 * (attempt + 1)
                print(f"search page {page} attempt {attempt + 1} failed: {str(e)[:80]}; retrying in {wait}s")
                time.sleep(wait)
        if not codes:
            print(f"page {page}: no codes")
            break
        for code in codes:
            if code in seen:
                continue
            seen.add(code)
            p = None
            for attempt in range(4):
                try:
                    p = fetch_product(code)          # product endpoint: full data + all photos
                    break
                except requests.HTTPError as e:
                    if e.response is not None and e.response.status_code == 429:
                        print(f"  {code}: rate limited, sleeping 65s")
                        time.sleep(65)               # product endpoint: 100 calls/min, hard 429 above
                        continue
                    print(f"  {code}: fetch failed {str(e)[:60]}")
                    break
                except requests.RequestException as e:
                    print(f"  {code}: fetch failed {str(e)[:60]}")
                    time.sleep(5)
                    break
            time.sleep(1.2)
            if not p:
                continue
            label = to_label(p)
            imgs = label.pop("images")
            if not imgs.get("nutrition") or not imgs.get("ingredients"):
                continue                       # we need photos to test extraction
            if label["per_100"].get("total_sugars_g") is None or not label["ingredients_text"]:
                continue
            paths = {}
            ok = True
            for kind in ("front", "ingredients", "nutrition"):
                if imgs.get(kind):
                    dest = IMG / f"{code}_{kind}.jpg"
                    if download(imgs[kind], dest):
                        paths[kind] = str(dest.relative_to(ROOT))
                    elif kind != "front":
                        ok = False
            if not ok:
                continue
            label["ingredients"] = split_ingredients(label["ingredients_text"])
            problems = sanity(label)
            dropped = drop_implausible(label)          # keep the row, blank the impossible fields
            if dropped:
                problems = problems + [f"dropped {d}" for d in dropped]
            rows.append({"barcode": code, "label": label, "images": paths, "image_urls": imgs,
                         "off_sanity_problems": problems, "trust_off_as_truth": not problems})
            print(f"{len(rows):3d} {code} {label.get('brand')} | {label.get('product_name')} | sanity={'ok' if not problems else problems}")
            if len(rows) >= args.n:
                break
        if len(rows) >= args.n:
            break
        time.sleep(7.0)                              # stay under the search rate limit

    out = DATA / "testset.jsonl"
    with out.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    clean = sum(1 for r in rows if r["trust_off_as_truth"])
    print(f"\nWrote {len(rows)} products to {out} ({clean} pass OFF sanity, {len(rows) - clean} need hand-check).")
    print("Next: open eval/manual_labels.csv, fill the per-100 g truth for the hand-check rows from the photos.")

    # seed the manual-label sheet (only if absent, never overwrite hand work)
    ml = ROOT / "eval" / "manual_labels.csv"
    if not ml.exists():
        import csv
        cols = ["barcode", "product_name", "checked_by_hand", "condition", "serving_size_g", "energy_kcal", "protein_g",
                "carbohydrate_g", "total_sugars_g", "added_sugars_g", "dietary_fibre_g", "total_fat_g",
                "saturated_fat_g", "trans_fat_g", "sodium_mg", "n_added_sugar_lines", "front_claims", "notes"]
        with ml.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            for r in rows:
                L = r["label"]
                w.writerow({"barcode": r["barcode"], "product_name": L.get("product_name"), "checked_by_hand": "",
                            "condition": "", "serving_size_g": L.get("serving_size_g"),
                            **{k: L["per_100"].get(k) for k in cols[5:15]},
                            "n_added_sugar_lines": "", "front_claims": "", "notes": "; ".join(r["off_sanity_problems"])})
        print(f"Seeded {ml} with OFF values. Verify each row against the photos and set checked_by_hand=1.")


if __name__ == "__main__":
    main()
