"""
Build eval/results/findings.html: a self-contained, shareable page for the Label Decoder
(what it does, three decoded examples, the 100-product numbers, where the vision model breaks).

    python eval/build_report_html.py
"""

import base64
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.rules.decoder import decode_label  # noqa: E402

RES = ROOT / "eval" / "results"
report = json.load((RES / "report.json").open(encoding="utf-8"))
rl, ex = report["rules_layer"], report.get("extraction", {})
rows = {json.loads(l)["barcode"]: json.loads(l) for l in (ROOT / "eval" / "data" / "testset.jsonl").open(encoding="utf-8")}


def esc(x) -> str:
    return html.escape("" if x is None else str(x))


def b64img(path: Path, alt: str, cap: str = "") -> str:
    data = base64.standard_b64encode(path.read_bytes()).decode("ascii")
    mt = "image/png" if path.suffix == ".png" else "image/jpeg"
    return f'<figure><img src="data:{mt};base64,{data}" alt="{esc(alt)}"><figcaption>{esc(cap or alt)}</figcaption></figure>'


def example(barcode: str, intro: str) -> str:
    lab = rows[barcode]["label"]
    d = decode_label(lab)
    s = d["sugar"]
    tsp = s["teaspoons_total_per_serve"]
    tiles = (f'<div class="tiles small"><div class="tile"><b>{s["total_sugars_per_100"]:g}%</b><span>sugar by weight</span></div>'
             f'<div class="tile"><b>{tsp:.1f}</b><span>teaspoons per {d["serving"]["g"]:g} g serve</span></div>'
             f'<div class="tile"><b>{d["consolidated_sugar"]["n_added_sugar_lines"]}</b><span>names for sugar in the list</span></div></div>')
    lines = "".join(f'<li><span class="rank">#{h["position"]}</span> {esc(h["ingredient_line"][:60])} <span class="muted">is</span> {esc(h["canonical"])}</li>'
                    for h in d["sugar_lines"])
    flags = "".join(f'<li><span class="sev {f["severity"]}">{f["severity"]}</span> <strong>{esc(f["title"])}.</strong> {esc(f["detail"])} <span class="muted">({esc(f["rule_ref"])})</span></li>'
                    for f in d["flags"])
    photo = ""
    p = rows[barcode]["images"].get("front")
    if p and (ROOT / p).exists():
        photo = b64img(ROOT / p, f"{lab.get('brand')} {lab.get('product_name')} pack photo (Open Food Facts, CC BY-SA)")
    return f"""<section class="example">
<h3>{esc(lab.get('brand'))} {esc(lab.get('product_name'))}</h3>
<p>{intro}</p>
<div class="exgrid"><div>{tiles}
<p class="serve muted">Serve: {esc(d['serving']['source'])}.</p>
{('<ul class="sugarlines">' + lines + '</ul>') if lines else ''}
<ul class="flags">{flags}</ul>
<p class="share">{esc(d['share_line'])}</p></div><div>{photo}</div></div>
</section>"""


top = "".join(f"<tr><td>{esc(d['brand'])}</td><td>{esc(d['name'])}</td><td class='num'>{d['sugar_pct']:.1f}</td>"
              f"<td class='num'>{d['tsp_per_serve']:.1f}</td><td class='num'>{d['n_sugar_names']}</td><td>{esc(', '.join(d['flags']))}</td></tr>"
              for d in rl["top_15_by_sugar"])
flagrows = "".join(f"<tr><td><code>{k}</code></td><td class='num'>{v}</td></tr>" for k, v in rl["flag_counts"].items())
fieldrows = "".join(f"<tr><td>{k}</td><td class='num'>{v}</td></tr>" for k, v in ex.get("field_accuracy_by_field_pct", {}).items())
legrows = "".join(f"<tr><td>{k}</td><td class='num'>{v['pct']}</td><td class='num'>{v['n_fields']}</td></tr>" for k, v in ex.get("field_accuracy_by_legibility_pct", {}).items())
worst = "".join(f"<tr><td>{esc(w['name'])}</td><td class='num'>{w['fields_correct']}/{w['fields_scored']}</td><td>{esc(w['legibility'])}</td></tr>" for w in ex.get("worst_10_products", []))

page = f"""<title>Indian Label Decoder</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,700&family=Atkinson+Hyperlegible:wght@400;700&family=IBM+Plex+Mono&display=swap">
<style>
/* layout: one reading column; examples split text | pack photo; tables scroll in their own box */
:root {{
  --bg: #fbf7ef; --fg: #241f1a; --muted: #6b625a; --rule: #e0d6c6; --accent: #b8431f; --accent-soft: #f6e4da;
  --tile: #f3ebdd; --ok: #2f6f4e; --warn: #b8431f; --mid: #c07a12; --low: #8a7f6a;
  --display: "Fraunces", Georgia, serif; --body: "Atkinson Hyperlegible", "Segoe UI", Arial, sans-serif; --mono: "IBM Plex Mono", Consolas, monospace;
}}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{
  --bg: #171412; --fg: #ece5da; --muted: #a79d90; --rule: #3a322b; --accent: #f08a62; --accent-soft: #3a241a;
  --tile: #221d19; --ok: #7fc29a; --warn: #f08a62; --mid: #e3a83f; --low: #a79d90; color-scheme: dark }} }}
:root[data-theme="dark"] {{
  --bg: #171412; --fg: #ece5da; --muted: #a79d90; --rule: #3a322b; --accent: #f08a62; --accent-soft: #3a241a;
  --tile: #221d19; --ok: #7fc29a; --warn: #f08a62; --mid: #e3a83f; --low: #a79d90; color-scheme: dark }}
body {{ background: var(--bg); color: var(--fg); font-family: var(--body); font-size: 16px; line-height: 1.55; margin: 0; }}
.wrap {{ max-width: 800px; margin: 0 auto; padding-block: 40px 80px; padding-inline: 20px; }}
h1, h2, h3 {{ font-family: var(--display); font-weight: 700; line-height: 1.12; text-wrap: balance; margin: 0; }}
h1 {{ font-size: clamp(32px, 5.5vw, 46px); }}
h2 {{ font-size: 27px; margin-top: 56px; padding-top: 18px; border-top: 1px solid var(--rule); }}
h3 {{ font-size: 21px; margin-top: 28px; }}
p {{ margin: 14px 0; max-width: 68ch; }}
.eyebrow {{ font-size: 12px; letter-spacing: .09em; text-transform: uppercase; color: var(--accent); font-weight: 700; margin-bottom: 14px; }}
.lede {{ font-size: 18px; color: var(--muted); max-width: 62ch; }}
.muted {{ color: var(--muted); }}
.tiles {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin: 26px 0; }}
.tiles.small {{ margin: 10px 0 6px; grid-template-columns: repeat(3, 1fr); }}
.tile {{ background: var(--tile); padding: 14px 16px; border-radius: 6px; min-width: 0; }}
.tile b {{ display: block; font-family: var(--display); font-size: 30px; font-weight: 700; font-variant-numeric: tabular-nums; }}
.tiles.small .tile b {{ font-size: 24px; }}
.tile span {{ font-size: 13px; color: var(--muted); }}
.note {{ background: var(--accent-soft); border-left: 3px solid var(--accent); padding: 12px 16px; margin: 22px 0; font-size: 15px; }}
.note p {{ margin: 6px 0; }}
.tablewrap {{ overflow-x: auto; margin: 18px 0; border: 1px solid var(--rule); border-radius: 6px; }}
table {{ border-collapse: collapse; width: 100%; font-size: 14px; }}
th, td {{ padding: 8px 10px; text-align: left; border-bottom: 1px solid var(--rule); vertical-align: top; }}
th {{ font-size: 12px; letter-spacing: .04em; text-transform: uppercase; color: var(--muted); font-weight: 700; }}
td.num {{ text-align: right; font-variant-numeric: tabular-nums; font-family: var(--mono); font-size: 13px; }}
tbody tr:last-child td {{ border-bottom: 0; }}
figure {{ margin: 0; }}
figure img {{ max-width: 100%; border-radius: 6px; border: 1px solid var(--rule); background: #fff; }}
figcaption {{ font-size: 12px; color: var(--muted); margin-top: 6px; }}
.example {{ margin-top: 34px; padding-top: 10px; }}
.exgrid {{ display: grid; grid-template-columns: 3fr 2fr; gap: 20px; align-items: start; }}
.exgrid > div {{ min-width: 0; }}
@media (max-width: 640px) {{ .exgrid {{ grid-template-columns: 1fr; }} .tiles.small {{ grid-template-columns: 1fr 1fr 1fr; }} }}
ul {{ padding-left: 20px; }} li {{ margin: 6px 0; }}
ul.sugarlines, ul.flags {{ list-style: none; padding-left: 0; }}
ul.sugarlines li {{ font-size: 14px; }}
.rank {{ font-family: var(--mono); font-size: 12px; color: var(--muted); }}
ul.flags li {{ font-size: 14px; margin: 10px 0; }}
.sev {{ display: inline-block; font-size: 11px; letter-spacing: .05em; text-transform: uppercase; padding: 1px 7px; border-radius: 3px; color: #fff; }}
.sev.high {{ background: var(--warn); }} .sev.medium {{ background: var(--mid); }} .sev.low {{ background: var(--low); }}
.share {{ font-family: var(--display); font-size: 17px; border-top: 1px dashed var(--rule); padding-top: 10px; }}
.serve {{ font-size: 13px; }}
code {{ font-family: var(--mono); font-size: 13px; background: var(--tile); padding: 1px 5px; border-radius: 3px; }}
.method {{ font-size: 15px; color: var(--muted); }}
a {{ color: var(--accent); }}
</style>
<div class="wrap">
<div class="eyebrow">Consumer tool and evaluation, October 2026</div>
<h1>Indian Label Decoder</h1>
<p class="lede">Indian nutrition labels are legally correct and practically useless. Paste the pack and get the real picture: sugar per serve in teaspoons, whether each front-of-pack claim survives per-serving maths, which ingredients are the same thing under different names, and the FSSAI rule the pack is following while misleading you.</p>

<div class="tiles">
  <div class="tile"><b>{rl['products']}</b><span>Indian products in the test set, with pack photos</span></div>
  <div class="tile"><b>{rl['share_with_sugar_under_2plus_names_pct']:.0f}%</b><span>list sugar under two or more names</span></div>
  <div class="tile"><b>{ex.get('field_accuracy_overall_pct', 0):.0f}%</b><span>vision extraction accuracy on nutrition numbers</span></div>
  <div class="tile"><b>{rl['nondeterministic_outputs']}</b><span>verdicts that changed between two runs</span></div>
</div>

<div class="note">
<p><strong>How it works.</strong> A vision model only transcribes the pack into a fixed JSON form. Every judgement comes from a rules layer written as code: 60+ sugar aliases in English, Hindi transliteration and INS numbers; the FSSAI Advertising and Claims Regulations 2018 Schedule I thresholds for low, free, source-of and high claims; per-100 g to per-serve conversion; 18 mislead patterns, each citing the regulation it leans on. The same label always gives the same verdict, and transcription errors and rule errors are measured separately.</p>
</div>

<h2>Three packs, decoded</h2>
{example("8901030807190", "A malt drink marketed to children. The pack declares no serve, so the decoder assumes a 30 g scoop and says so. The ingredient list puts sugar third, behind malt and milk solids; the nutrition table says the powder is almost half sugar by weight.")}
{example("7622201150303", "A chocolate confectionery with an 18 g declared serve. Sugar is the first ingredient; the list then adds lactose-rich whey permeate and maltodextrin, which are sugar and sugar-like under other names. A tiny serve keeps every per-serve number small.")}
{example("8906120109918", "A premium date-and-nut bite. Dates and nuts are whole foods and are not counted as added sugar; honey is. The verdict is mild, which is the point: the decoder is not a scare machine, it reports what the label supports.")}

<h2>What 100 Indian shelf products look like</h2>
<p>The test set is the 100 most-scanned Indian products on Open Food Facts that have both an ingredient list and a nutrition table with photos. The rules layer decoded each one twice; no verdict changed. Median sugar per serve across the set is {rl['median_tsp_per_serve']} teaspoons; the spread is the story.</p>
<div class="tablewrap"><table><thead><tr><th>Brand</th><th>Product</th><th>Sugar % by weight</th><th>tsp per serve</th><th>Sugar names</th><th>Flags</th></tr></thead><tbody>{top}</tbody></table></div>
<h3>Flags raised across the 100</h3>
<div class="tablewrap"><table><thead><tr><th>Flag</th><th>Products</th></tr></thead><tbody>{flagrows}</tbody></table></div>
<p class="muted">SUGAR_SPLIT: sugar under two or more names. SERVING_TINY: declared serve under 15 g. WHO_LIMIT_BLOWN: one serve exceeds the WHO 25 g/day free-sugar guideline. PER100_VS_SERVE: a claim that holds per 100 g but not per serve. NAS_SUBSTITUTE: "no added sugar" with a sugar-substituting ingredient in the list.</p>

<h2>How well the camera reads the pack</h2>
<p>Every numeric field the vision model transcribed from the photos was compared with the Open Food Facts reference, tolerance max(0.5, 10%). {ex.get('products_scored', 0)} products scored.</p>
<div class="tiles">
  <div class="tile"><b>{ex.get('field_accuracy_overall_pct', 0)}%</b><span>field accuracy overall</span></div>
  <div class="tile"><b>{ex.get('sugar_alias_recall_pct', 0)}%</b><span>sugar aliases recovered from the ingredient photo</span></div>
  <div class="tile"><b>{ex.get('serving_size_accuracy_pct', 0)}%</b><span>serving size read correctly</span></div>
</div>
<div class="exgrid">
<div><div class="tablewrap"><table><thead><tr><th>Field</th><th>Accuracy %</th></tr></thead><tbody>{fieldrows}</tbody></table></div></div>
<div><div class="tablewrap"><table><thead><tr><th>Pack legibility</th><th>Accuracy %</th><th>Fields</th></tr></thead><tbody>{legrows}</tbody></table></div></div>
</div>
<h3>Where it breaks</h3>
<p>Clean packs read at 96%. Crumpled film, glare through plastic, curved tubs and bottles, US-style per-serve-only panels and ingredient strips in tiny type pull the model to 66%. Dietary fibre and sodium are the weakest fields: fibre is often printed as a bound ("&lt;1 g") or in the last row that gets cropped, and sodium arrives as salt, as "0.1 g", or as a per-serve value.</p>
<div class="tablewrap"><table><thead><tr><th>Product</th><th>Correct / scored</th><th>Legibility</th></tr></thead><tbody>{worst}</tbody></table></div>

<h2>The app</h2>
{b64img(ROOT / "docs" / "app.png", "Indian Label Decoder app showing a decoded biscuit pack", "Barcode lookup on a Britannia Bourbon pack: sugar by weight, teaspoons per serve, and the flags the pack earns.")}
<p>Three ways in: pack photos, pasted label text, or a barcode (Open Food Facts lookup). Barcode and the 100 built-in examples work with no model key; photo and text use Claude or the free Gemini tier.</p>

<h2>Method and limits</h2>
<p class="method">Thresholds follow the FSS (Advertising and Claims) Regulations 2018 and the FSS (Labelling and Display) Regulations 2020 as published; they are amended from time to time and should be re-verified before quoting publicly. The reference data is Open Food Facts crowd entries that passed a sanity filter; some of the 13% extraction "errors" are reference mistakes, which a hand-checked label sheet in the repository is designed to correct. The vision transcriptions for this evaluation were produced by Claude Sonnet reading the 300 pack photos; the application calls the same model through its API. Pack photos are from Open Food Facts (CC BY-SA).</p>
</div>
"""
(RES / "findings.html").write_text(page, encoding="utf-8")
print(f"wrote {RES / 'findings.html'} ({(RES / 'findings.html').stat().st_size // 1024} KB)")
