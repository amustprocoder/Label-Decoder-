"""
Evaluation harness for the Label Decoder.

Two layers, scored separately because they fail for different reasons:

  1. Extraction accuracy (needs a model key): run src/extract.py on the pack photos and compare
     every numeric field against the reference. Reference = manual_labels.csv rows marked
     checked_by_hand=1 (preferred), else OFF rows that pass sanity(). A field counts as correct
     when |pred - ref| <= max(0.5, 10% of ref). Ingredient-list accuracy = recall of the sugar
     aliases found in the reference ingredient text. Results are broken down by the `condition`
     column (good / low_light / glare / regional_language / crumpled ...) that you tag by hand,
     plus by image resolution, so "where it breaks" is a table, not an impression.

  2. Rules-layer determinism (no key needed): decode every reference label twice, assert
     identical output, and report the distribution of flags across the test set. This is the
     "what does the Indian shelf actually look like" number that goes in the launch post.

    python eval/run_eval.py                 # both layers (extraction skipped if no key)
    python eval/run_eval.py --rules-only
    python eval/run_eval.py --limit 20      # cheaper first pass
Writes eval/results/extraction_<provider>.jsonl, eval/results/report.json, eval/results/report.md
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.llm import model_id, provider  # noqa: E402
from src.rules.decoder import decode_label, split_ingredients  # noqa: E402
from src.rules.sugar_aliases import find_sugars  # noqa: E402

DATA = ROOT / "eval" / "data"
RES = ROOT / "eval" / "results"
FIELDS = ["energy_kcal", "protein_g", "carbohydrate_g", "total_sugars_g", "dietary_fibre_g", "total_fat_g",
          "saturated_fat_g", "sodium_mg"]


def load_testset() -> list[dict]:
    rows = [json.loads(l) for l in (DATA / "testset.jsonl").open(encoding="utf-8")]
    manual = {}
    ml = ROOT / "eval" / "manual_labels.csv"
    if ml.exists():
        for r in csv.DictReader(ml.open(encoding="utf-8")):
            if str(r.get("checked_by_hand", "")).strip() in ("1", "y", "yes", "true"):
                manual[r["barcode"]] = r
    for r in rows:
        m = manual.get(r["barcode"])
        if m:
            per100 = {}
            for k in FIELDS + ["added_sugars_g", "trans_fat_g"]:
                v = (m.get(k) or "").strip()
                if v:
                    per100[k] = float(v)
            r["reference"] = dict(r["label"], per_100=per100,
                                  serving_size_g=float(m["serving_size_g"]) if (m.get("serving_size_g") or "").strip() else r["label"].get("serving_size_g"))
            r["reference_source"] = "manual"
            r["condition"] = (m.get("condition") or "untagged").strip() or "untagged"
            r["usable"] = True
        else:
            r["reference"] = r["label"]
            r["reference_source"] = "off"
            r["condition"] = "untagged"
            r["usable"] = r["trust_off_as_truth"]
    return rows


def close(pred, ref) -> bool | None:
    if ref is None:
        return None
    if pred is None:
        return False
    return abs(pred - ref) <= max(0.5, 0.10 * abs(ref))


def image_bucket(paths: dict) -> str:
    try:
        from PIL import Image
        p = paths.get("nutrition")
        if not p:
            return "no_image"
        w, h = Image.open(ROOT / p).size
        px = max(w, h)
        return "<400px" if px < 400 else "400-800px" if px < 800 else ">=800px"
    except Exception:
        return "unknown"


def run_extraction(rows: list[dict], limit: int | None) -> dict:
    from src.extract import extract_from_images
    prov = provider()
    out_path = RES / f"extraction_{prov}.jsonl"
    done = {}
    if out_path.exists():
        for l in out_path.open(encoding="utf-8"):
            d = json.loads(l)
            done[d["barcode"]] = d
    fh = out_path.open("a", encoding="utf-8")
    n = 0
    for r in rows:
        if limit and n >= limit:
            break
        n += 1
        if r["barcode"] in done:
            continue
        imgs = [str(ROOT / r["images"][k]) for k in ("front", "ingredients", "nutrition") if k in r["images"]]
        t0 = time.time()
        try:
            pred = extract_from_images(imgs)
            err = None
        except Exception as e:
            pred, err = None, str(e)
        rec = {"barcode": r["barcode"], "pred": pred, "error": err, "seconds": round(time.time() - t0, 1),
               "model": model_id(prov)}
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        fh.flush()
        done[r["barcode"]] = rec
        print(f"  {n:3d} {r['barcode']} {'ok' if not err else 'ERR ' + err[:60]} ({rec['seconds']}s)")
    fh.close()
    return done


def score_extraction(rows: list[dict], preds: dict) -> dict:
    field_hits = defaultdict(lambda: [0, 0])          # field -> [correct, scored]
    by_cond = defaultdict(lambda: [0, 0])
    by_res = defaultdict(lambda: [0, 0])
    by_leg = defaultdict(lambda: [0, 0])          # model's own legibility verdict: good / partial / poor
    by_lang = defaultdict(lambda: [0, 0])         # label language the model saw
    sugar_recall = [0, 0]
    claims_found = [0, 0]
    serving_hits = [0, 0]
    errors = 0
    per_product = []
    for r in rows:
        if not r["usable"] or r["barcode"] not in preds:
            continue
        p = preds[r["barcode"]]
        if p.get("error") or not p.get("pred"):
            errors += 1
            continue
        pred, ref = p["pred"], r["reference"]
        correct = scored = 0
        for f in FIELDS:
            c = close(pred["per_100"].get(f), ref["per_100"].get(f))
            if c is None:
                continue
            scored += 1
            field_hits[f][1] += 1
            if c:
                correct += 1
                field_hits[f][0] += 1
        by_cond[r["condition"]][0] += correct
        by_cond[r["condition"]][1] += scored
        b = image_bucket(r["images"])
        by_res[b][0] += correct
        by_res[b][1] += scored
        leg = pred.get("legibility") or "unknown"
        by_leg[leg][0] += correct
        by_leg[leg][1] += scored
        lang = (pred.get("language") or "unknown").lower().replace(" ", "")
        lang = "en" if lang in ("en", "english") else ("multilingual" if ("+" in lang or "," in lang) else lang)
        by_lang[lang][0] += correct
        by_lang[lang][1] += scored
        if ref.get("serving_size_g"):
            serving_hits[1] += 1
            if close(pred.get("serving_size_g"), ref["serving_size_g"]):
                serving_hits[0] += 1
        ref_sugars = {h.canonical for h in find_sugars(split_ingredients(ref["ingredients_text"]))}
        pred_items = pred.get("ingredients") or split_ingredients(pred.get("ingredients_text") or "")
        pred_sugars = {h.canonical for h in find_sugars(pred_items)}
        sugar_recall[0] += len(ref_sugars & pred_sugars)
        sugar_recall[1] += len(ref_sugars)
        claims_found[1] += 1
        claims_found[0] += 1 if pred.get("front_of_pack_claims") else 0
        per_product.append({"barcode": r["barcode"], "name": ref.get("product_name"), "fields_correct": correct,
                            "fields_scored": scored, "condition": r["condition"], "legibility": pred.get("legibility"),
                            "language": pred.get("language")})

    def pct(a, b):
        return None if not b else round(100.0 * a / b, 1)

    total_c = sum(v[0] for v in field_hits.values())
    total_s = sum(v[1] for v in field_hits.values())
    worst = sorted(per_product, key=lambda x: (x["fields_correct"] / x["fields_scored"]) if x["fields_scored"] else 1)[:10]
    return {
        "products_scored": len(per_product), "extraction_errors": errors,
        "field_accuracy_overall_pct": pct(total_c, total_s),
        "field_accuracy_by_field_pct": {f: pct(*v) for f, v in field_hits.items()},
        "field_accuracy_by_condition_pct": {c: {"pct": pct(*v), "n_fields": v[1]} for c, v in by_cond.items()},
        "field_accuracy_by_image_resolution_pct": {c: {"pct": pct(*v), "n_fields": v[1]} for c, v in by_res.items()},
        "field_accuracy_by_legibility_pct": {c: {"pct": pct(*v), "n_fields": v[1]} for c, v in by_leg.items()},
        "field_accuracy_by_language_pct": {c: {"pct": pct(*v), "n_fields": v[1]} for c, v in by_lang.items()},
        "serving_size_accuracy_pct": pct(*serving_hits),
        "sugar_alias_recall_pct": pct(*sugar_recall),
        "share_with_any_claim_captured_pct": pct(*claims_found),
        "worst_10_products": worst,
    }


def rules_layer(rows: list[dict]) -> dict:
    flags = Counter()
    sev = Counter()
    tsp = []
    split = 0
    claim_verdicts = Counter()
    nondeterministic = 0
    decoded = []
    for r in rows:
        lab = r["reference"]
        a, b = decode_label(lab), decode_label(lab)
        if a != b:
            nondeterministic += 1
        for f in a["flags"]:
            flags[f["code"]] += 1
            sev[f["severity"]] += 1
        for c in a["claims"]:
            claim_verdicts[c["verdict"]] += 1
        if a["consolidated_sugar"]["n_added_sugar_lines"] >= 2:
            split += 1
        if a["sugar"]["teaspoons_total_per_serve"] is not None:
            tsp.append(a["sugar"]["teaspoons_total_per_serve"])
        decoded.append({"barcode": r["barcode"], "name": lab.get("product_name"), "brand": lab.get("brand"),
                        "sugar_pct": lab["per_100"].get("total_sugars_g"), "tsp_per_serve": a["sugar"]["teaspoons_total_per_serve"],
                        "n_sugar_names": a["consolidated_sugar"]["n_added_sugar_lines"],
                        "flags": [f["code"] for f in a["flags"]], "share_line": a["share_line"]})
    tsp_sorted = sorted(tsp)
    top = sorted(decoded, key=lambda d: -(d["sugar_pct"] or 0))[:15]
    return {
        "products": len(rows), "nondeterministic_outputs": nondeterministic,
        "products_with_sugar_under_2plus_names": split,
        "share_with_sugar_under_2plus_names_pct": round(100.0 * split / max(1, len(rows)), 1),
        "median_tsp_per_serve": round(tsp_sorted[len(tsp_sorted) // 2], 1) if tsp_sorted else None,
        "flag_counts": dict(flags.most_common()), "severity_counts": dict(sev),
        "claim_verdicts": dict(claim_verdicts),
        "top_15_by_sugar": top,
        "all_decoded": decoded,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rules-only", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--preds", help="score an existing predictions JSONL ({barcode, pred, error, model} per line) instead of calling a model")
    args = ap.parse_args()
    RES.mkdir(parents=True, exist_ok=True)
    rows = load_testset()
    usable = [r for r in rows if r["usable"]]
    print(f"Test set: {len(rows)} products, {len(usable)} with trusted reference "
          f"({sum(1 for r in rows if r['reference_source'] == 'manual')} hand-checked).")

    report = {"rules_layer": rules_layer(rows)}
    rl = report["rules_layer"]
    print(f"\n=== Rules layer ===\n{rl['products']} products decoded twice, {rl['nondeterministic_outputs']} differed.")
    print(f"Sugar under 2+ names: {rl['products_with_sugar_under_2plus_names']} ({rl['share_with_sugar_under_2plus_names_pct']}%)")
    print(f"Median teaspoons per serve: {rl['median_tsp_per_serve']}")
    print("Flags:", ", ".join(f"{k}={v}" for k, v in rl["flag_counts"].items()))

    if not args.rules_only:
        if args.preds:
            preds = {}
            for l in open(args.preds, encoding="utf-8"):
                d = json.loads(l)
                preds[d["barcode"]] = d
            print(f"\n=== Extraction scored from {args.preds} ({len(preds)} predictions, model {next(iter(preds.values())).get('model')}) ===")
        elif provider() is None:
            print("\n(no model key: skipping extraction accuracy; set ANTHROPIC_API_KEY or GEMINI_API_KEY, or pass --preds)")
            preds = None
        else:
            print(f"\n=== Extraction with {provider()} / {model_id(provider())} ===")
            preds = run_extraction(usable, args.limit)
        if preds:
            ex = score_extraction(usable, preds)
            report["extraction"] = ex
            print(f"Field accuracy: {ex['field_accuracy_overall_pct']}% over {ex['products_scored']} products")
            for f, v in ex["field_accuracy_by_field_pct"].items():
                print(f"  {f:18s} {v}%")
            print("By condition:", ex["field_accuracy_by_condition_pct"])
            print("By resolution:", ex["field_accuracy_by_image_resolution_pct"])
            print(f"Sugar alias recall: {ex['sugar_alias_recall_pct']}%  Serving size: {ex['serving_size_accuracy_pct']}%")

    (RES / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    write_md(report)
    print(f"\nReport: {RES / 'report.md'}")


def write_md(report: dict) -> None:
    rl = report["rules_layer"]
    md = ["# Label Decoder: evaluation report", "",
          f"Test set: {rl['products']} Indian products from Open Food Facts (photos + structured data).", "",
          "## Rules layer (deterministic)", "",
          f"- Decoded twice, outputs differed: **{rl['nondeterministic_outputs']}**",
          f"- Products with sugar under 2+ names: **{rl['products_with_sugar_under_2plus_names']}** ({rl['share_with_sugar_under_2plus_names_pct']}%)",
          f"- Median teaspoons of sugar per serve: **{rl['median_tsp_per_serve']}**", "",
          "| Flag | Products |", "|---|---|"] + [f"| {k} | {v} |" for k, v in rl["flag_counts"].items()]
    md += ["", "### Top 15 by sugar", "", "| Brand | Product | Sugar % | tsp/serve | Sugar names | Flags |", "|---|---|---|---|---|---|"]
    for d in rl["top_15_by_sugar"]:
        md.append(f"| {d['brand']} | {d['name']} | {d['sugar_pct'] if d['sugar_pct'] is None else round(d['sugar_pct'], 1)} | "
                  f"{d['tsp_per_serve'] if d['tsp_per_serve'] is None else round(d['tsp_per_serve'], 1)} | {d['n_sugar_names']} | {', '.join(d['flags'])} |")
    ex = report.get("extraction")
    if ex:
        md += ["", "## Extraction accuracy (vision model vs reference)", "",
               f"- Products scored: **{ex['products_scored']}** (errors: {ex['extraction_errors']})",
               f"- Field accuracy overall: **{ex['field_accuracy_overall_pct']}%** (tolerance max(0.5, 10%))",
               f"- Sugar alias recall: **{ex['sugar_alias_recall_pct']}%**",
               f"- Serving size accuracy: **{ex['serving_size_accuracy_pct']}%**", "",
               "| Field | Accuracy % |", "|---|---|"] + [f"| {f} | {v} |" for f, v in ex["field_accuracy_by_field_pct"].items()]
        md += ["", "### Where it breaks", "", "| Condition | Accuracy % | Fields |", "|---|---|---|"]
        md += [f"| {c} | {v['pct']} | {v['n_fields']} |" for c, v in ex["field_accuracy_by_condition_pct"].items()]
        md += ["", "| Image resolution | Accuracy % | Fields |", "|---|---|---|"]
        md += [f"| {c} | {v['pct']} | {v['n_fields']} |" for c, v in ex["field_accuracy_by_image_resolution_pct"].items()]
        md += ["", "| Legibility (model's own verdict) | Accuracy % | Fields |", "|---|---|---|"]
        md += [f"| {c} | {v['pct']} | {v['n_fields']} |" for c, v in ex["field_accuracy_by_legibility_pct"].items()]
        md += ["", "| Label language | Accuracy % | Fields |", "|---|---|---|"]
        md += [f"| {c} | {v['pct']} | {v['n_fields']} |" for c, v in ex["field_accuracy_by_language_pct"].items()]
        md += ["", "### Worst 10 products", "", "| Barcode | Product | Correct/Scored | Condition | Legibility |", "|---|---|---|---|---|"]
        md += [f"| {w['barcode']} | {w['name']} | {w['fields_correct']}/{w['fields_scored']} | {w['condition']} | {w['legibility']} |" for w in ex["worst_10_products"]]
    (RES / "report.md").write_text("\n".join(md) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
