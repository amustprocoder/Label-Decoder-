"""
Build the static (Netlify) version of the Label Decoder.

    python build_static.py            # writes site/  (drag that folder onto Netlify)

Every one of the 100 test-set packs is decoded here, once, with the same rules layer and the
same HTML builders (src/ui.py) the Streamlit app uses, so both versions look and answer the
same. The page then only swaps pre-rendered HTML, which is why it opens instantly and never
sleeps. Photo and pasted-text input need a model, so the static page links to the live
Streamlit app for those.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src import ui  # noqa: E402
from src.rules.decoder import decode_label  # noqa: E402

OUT = ROOT / "site"
GITHUB = "https://github.com/amustprocoder/Label-Decoder-"
SITE = "https://labeldecoder-omrana.netlify.app"   # where this folder is deployed; link previews need the full URL
LIVE = None       # URL of the Streamlit app once it is deployed; None keeps the site free of dead links
PREDS = ROOT / "eval" / "results" / "extraction_claude-subagents.jsonl"   # the AI's recorded photo readings
# Recorded photo readings shown in "Watch the AI read": (barcode, chip label, chip is a miss?, summary override)
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
FEATURED = ["7622201150303", "8901063093287", "8906080603938", "8901719125478",
            "8904004400212", "8901058006292", "8906059638329", "6294017124031"]
MARQUEE = [
    ("Horlicks", "is almost half sugar. 3.5 spoons in one scoop."),
    ("Cadbury Shots", "72% sugar, hidden under 2 names."),
    ("1 in 5 packs", "cut sugar into pieces so it never looks like #1."),
    ("Soya Chips", "say “rich in protein”. One serve = 7% of your day."),
    ("Paper Boat", "1 bottle = more sugar than a whole day should have."),
    ("Maggi", "1 pack = a third of a day's salt."),
]


def result_html(label: dict, result: dict, img: str | None, all_sugar: list[float], code: str) -> str:
    """Same card order as render() in app.py."""
    liquid = result["product"]["is_liquid"]
    lights = ui._lights(label.get("per_100") or {}, liquid)
    flags = [f for f in result["flags"] if not (result["claims"] and f["code"] in ("PER100_VS_SERVE", "CLAIM_FAILS"))]
    share = (f'<div class="ld-share"><a class="ld-btn" href="share/{code}.png" download="label-decoder-{code}.png">'
             f'{ui.icon("download")} Share card (PNG)</a><span>Get this as a picture. Send it on WhatsApp or post it.</span></div>')
    more = (ui.rank_card(result, all_sugar) + ui.lights_card(lights, liquid)
            + ui.claims_card(result["claims"], result["serving"]["g"], "ml" if liquid else "g") + ui.flags_card(flags)
            + ui.order_card(label, result) + ui.sugar_names_card(label, result) + ui.honest_card(result))
    # the verdict, three facts and the spoons come first; the rest follows in the same scroll
    return (ui.top_card(label, result, img, lights) + ui.three_things(result, lights) + ui.sugar_cards(result)
            + more
            + share)


def og_image() -> bytes:
    """1200x630 link-preview card (LinkedIn, WhatsApp, X)."""
    from io import BytesIO
    from PIL import Image, ImageDraw, ImageFont

    def font(size: int, bold: bool = True):
        names = (["arialbd.ttf", "DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"] if bold
                 else ["arial.ttf", "DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"])
        for n in names:
            try:
                return ImageFont.truetype(n, size)
            except OSError:
                continue
        return ImageFont.load_default()

    W, H = 1200, 630
    im = Image.new("RGB", (W, H), "#f4f6f9")
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 14], fill="#4338ca")
    d.text((70, 62), "INDIAN LABEL DECODER", font=font(26), fill="#4338ca")
    d.text((70, 112), "Healthy on the front.", font=font(84), fill="#1c1917")
    d.text((70, 208), "Sugar", font=font(84), fill="#dc2626")
    d.text((70 + d.textlength("Sugar ", font=font(84)), 208), "on the back.", font=font(84), fill="#1c1917")
    d.text((70, 322), "Sugar in spoons, its secret names, and every pack claim", font=font(32, False), fill="#57534e")
    d.text((70, 364), "checked against Indian food law.", font=font(32, False), fill="#57534e")
    x = 70
    for _ in range(5):                                   # five sugar cubes, the product's signature visual
        d.rounded_rectangle([x, 440, x + 58, 498], radius=12, fill="#f1f5f9", outline="#94a3b8", width=4)
        x += 72
    x = 70
    for big, small in (("100", "Indian packs checked"), ("1 in 5", "hide sugar under 2+ names"), ("87%", "photo accuracy")):
        d.text((x, 530), big, font=font(38), fill="#1c1917")
        d.text((x + d.textlength(big + " ", font=font(38)), 542), small, font=font(24, False), fill="#57534e")
        x += d.textlength(big + " ", font=font(38)) + d.textlength(small, font=font(24, False)) + 46
    buf = BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def own_photo_card() -> str:
    """Where to go for a live upload: the Streamlit app if it is deployed, else the code."""
    if LIVE:
        return (f'<div class="ld-empty"><b>Want to try your own photo?</b><br>The live version reads any pack. '
                f'It takes about 30 seconds to wake up.<br><br><a class="ld-btn" href="{LIVE}" target="_blank">Open the live AI version →</a></div>')
    return (f'<div class="ld-empty"><b>Want to try your own photo?</b><br>Live upload needs an AI key, so it runs in the full app, '
            f'not on this page. The code and the run steps are on GitHub.<br><br>'
            f'<a class="ld-btn" href="{GITHUB}" target="_blank">See the code on GitHub →</a></div>')


def replays(rows: dict, all_sugar: list[float]) -> tuple[str, dict]:
    """Chip bar + {barcode: html} for the recorded photo readings: photos, field check, verdict from the reading."""
    preds = {json.loads(line)["barcode"]: json.loads(line)["pred"] for line in PREDS.open(encoding="utf-8")}
    chips, html = "", {}
    for i, (code, tag, miss, summary) in enumerate(REPLAYS):
        ref, pred = rows[code]["label"], dict(preds[code])
        imgs = rows[code].get("image_urls") or {}
        name = ui.full_name(ref.get("brand"), ref.get("product_name"))
        pred["barcode"] = code
        result = decode_label(pred)
        lights = ui._lights(pred.get("per_100") or {}, result["product"]["is_liquid"])
        card = ui.replay_card(name, imgs, ui.read_check(pred, ref), pred, summary)
        html[code] = (card + ui.top_card(pred, result, imgs.get("front"), lights) + ui.three_things(result, lights)
                      + ui.sugar_cards(result))
        chips += (f'<button data-code="{code}"{" class=on" if i == 0 else ""}>{ui.esc(name)}'
                  f'<i class="{"miss" if miss else ""}">{ui.esc(tag)}</i></button>')
    return f'<div class="ld-chips" id="rp-chips">{chips}</div>', html


EXTRA_CSS = """
<style>
.ld-tabs { display:flex; flex-wrap:wrap; gap:6px; background:#fff; border:1px solid var(--line); border-radius:999px; padding:5px; width:fit-content; max-width:100%; margin:6px 0 18px; }
.ld-tabs button { font:600 14.5px 'Inter',sans-serif; color:var(--muted); background:transparent; border:none; padding:8px 16px; border-radius:999px; cursor:pointer; transition:all .15s; }
.ld-tabs button:hover { background:#fafaf9; color:var(--ink); }
.ld-tabs button.on { color:#fff; background:linear-gradient(135deg,#334155,#0f172a); box-shadow:0 4px 12px rgba(15,23,42,.3); }
.ld-panel { display:none; } .ld-panel.on { display:block; }
.ld-grid4 { display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-bottom:6px; }
.ld-pc { background:var(--card); border:1px solid var(--line); border-radius:18px; padding:12px; cursor:pointer; transition:transform .18s, box-shadow .18s; }
.ld-pc:hover { transform:translateY(-3px); box-shadow:0 10px 24px rgba(28,25,23,.08); }
.ld-pc:hover img { transform:scale(1.07); }
.ld-pc.on { border-color:#818cf8; box-shadow:0 0 0 4px rgba(67,56,202,.15), 0 12px 28px rgba(15,23,42,.12); }
.ld-pc .go { margin-top:10px; text-align:center; font:700 14px 'Inter',sans-serif; border:1px solid var(--line); border-radius:999px; padding:8px; color:var(--ink); background:#fff; }
.ld-pc.on .go { background:linear-gradient(135deg,#334155,#0f172a); color:#fff; border:none; box-shadow:0 6px 16px rgba(15,23,42,.3); }
.ld-btn { display:inline-block; text-decoration:none; font:700 14.5px 'Inter',sans-serif; color:#fff; background:linear-gradient(135deg,#334155,#0f172a);
  border:none; border-radius:999px; padding:10px 20px; cursor:pointer; box-shadow:0 6px 16px rgba(15,23,42,.3); }
.ld-btn:hover { box-shadow:0 8px 20px rgba(15,23,42,.4); }
.ld-share { display:flex; align-items:center; gap:14px; flex-wrap:wrap; margin:16px 0 4px; }
.ld-share span { font-size:13.5px; color:var(--faint); }
.ld-field { display:flex; gap:10px; align-items:flex-end; margin-bottom:8px; }
.ld-field label { display:block; font-size:14px; color:var(--muted); margin-bottom:6px; }
.ld-field > div { flex:1; }
.ld-field input, .ld-field select { width:100%; box-sizing:border-box; font:15px 'Inter',sans-serif; color:var(--ink); background:#fff; border:1.5px solid var(--line); border-radius:14px; padding:12px 14px; outline:none; }
.ld-field input:focus, .ld-field select:focus { border-color:var(--brand); box-shadow:0 0 0 4px rgba(67,56,202,.15); }
.ld-cmp-grid { display:grid; grid-template-columns:1fr 1fr; gap:14px; }
.ld-msg { margin:12px 0; }
#packs, #how { scroll-margin-top:84px; }
/* handwritten notes in the page margins: only where there is real margin to write in */
.ld-page { position:relative; }
.ld-scribble { display:none; position:absolute; width:176px; font:600 24px/1.05 'Caveat',cursive; color:#475569; opacity:.5; pointer-events:none; }
.ld-scribble svg { display:block; margin-top:6px; }
.ld-scribble.l { left:-196px; transform:rotate(-7deg); text-align:right; } .ld-scribble.l svg { margin-left:auto; }
.ld-scribble.r { right:-200px; transform:rotate(5deg); }
@media (min-width: 1500px) { .ld-scribble { display:block; } }
html { scroll-behavior:smooth; }
/* ---- hero entrance: plays once on load. Text rises in, then the pack builds: front first, back fans out ---- */
.ld-ln { display:inline-block; }
@keyframes ld-rise { from { opacity:0; transform:translateY(22px); } }
.ld-hero .ld-badge, .ld-hero .ld-ln, .ld-hero p.sub, .ld-hero .ld-ctas, .ld-hero .ld-proof { animation:ld-rise .6s cubic-bezier(.2,.7,.2,1) both; }
.ld-hero .ld-badge { animation-delay:.05s; } .ld-hero .ld-ln { animation-delay:.16s; } .ld-hero .ld-ln ~ .ld-ln { animation-delay:.32s; }
.ld-hero p.sub { animation-delay:.52s; } .ld-hero .ld-ctas { animation-delay:.66s; } .ld-hero .ld-proof { animation-delay:.8s; }
.ld-face.front { animation:ld-front .7s cubic-bezier(.2,.8,.2,1) .35s both; }
@keyframes ld-front { from { opacity:0; transform:translateX(-46px) rotate(-16deg); } }
.ld-face.back { animation:ld-back .8s cubic-bezier(.2,.8,.2,1) .9s both; }
@keyframes ld-back { from { opacity:0; transform:translateX(-96px) rotate(-6deg) scale(.96); } }
.ld-pack-cap { animation:ld-rise .5s ease 1.6s both; }
.ld-live { animation:ld-rise .6s cubic-bezier(.2,.7,.2,1) 1s both; }
/* ---- tabs: the dark pill slides to the tab you click, and the new content fades in ---- */
.ld-tabs { position:relative; }
.ld-tabs button { position:relative; z-index:1; }
.ld-tabs.has-pill button.on { background:transparent; box-shadow:none; }
.ld-pill { position:absolute; z-index:0; border-radius:999px; background:linear-gradient(135deg,#334155,#0f172a); box-shadow:0 4px 12px rgba(15,23,42,.3);
  transition:left .34s cubic-bezier(.3,1.15,.4,1), top .34s cubic-bezier(.3,1.15,.4,1), width .34s cubic-bezier(.3,1.15,.4,1), height .34s; }
.ld-pill.still { transition:none; }
.ld-panel.on { animation:ld-tabin .34s ease both; }
@keyframes ld-tabin { from { opacity:0; transform:translateY(10px); } }
/* ---- traffic lights come on one by one, then the meaning line ---- */
.ld-lights .ld-light { animation:ld-lamp .5s cubic-bezier(.3,1.4,.5,1) both; }
.ld-lights .ld-light:nth-child(1) { animation-delay:.15s; } .ld-lights .ld-light:nth-child(2) { animation-delay:.42s; }
.ld-lights .ld-light:nth-child(3) { animation-delay:.69s; } .ld-lights .ld-light:nth-child(4) { animation-delay:.96s; }
@keyframes ld-lamp { from { opacity:0; transform:scale(.8); } }
.ld-lights + .ld-mean { animation:ld-in .45s ease 1.35s both; }
.rv:not(.in) .ld-mean { animation:none !important; }
/* ---- face-off: the winner lifts with a green ring and its medal pops; the other pack steps back ---- */
.ld-cmp.rv.in.win { transform:translateY(-6px); box-shadow:0 0 0 3px var(--green), 0 18px 36px rgba(22,163,74,.2); }
.ld-cmp.rv.in.lose { opacity:.6; }
.ld-cmp.win .win .ld-ic { display:inline-block; animation:ld-medal .7s cubic-bezier(.3,1.7,.5,1) .55s both; }
@keyframes ld-medal { from { opacity:0; transform:scale(0) rotate(-40deg); } }
@media (prefers-reduced-motion: reduce) {
  .ld-hero *, .ld-live, .ld-panel.on, .ld-lights .ld-light, .ld-lights + .ld-mean, .ld-cmp.win .win .ld-ic { animation:none !important; }
  .ld-pill { transition:none; }
}
/* ---- scroll reveal: a card stays hidden until it scrolls into view, then its own animation plays once ---- */
.ld-sp { position:fixed; top:0; left:0; height:3px; width:0; z-index:100; background:linear-gradient(90deg,#4338ca,#dc2626); }
.rv { animation:none !important; opacity:0; transform:translateY(24px); transition:opacity .6s ease, transform .6s cubic-bezier(.2,.7,.2,1); }
.rv.in { opacity:1; transform:none; }
.ld-pc.rv.in { transition:opacity .6s ease, transform .22s ease, box-shadow .18s; }
.ld-pc.rv.in:hover { transform:translateY(-3px); }
/* whatever is inside a hidden card waits with it */
.rv:not(.in) .ld-cube, .rv:not(.in) .ld-light, .rv:not(.in) .ld-bar > div, .rv:not(.in) .ld-hrow .t i, .rv:not(.in) .ld-dist i,
.rv:not(.in) .ld-ring .r, .rv:not(.in) .ld-stack i, .rv:not(.in) .ld-3 > div, .rv:not(.in) .ld-vban, .rv:not(.in) .ld-read tr,
.rv:not(.in) .ld-read .ok, .rv:not(.in) .ld-read .no, .rv:not(.in) .ld-ing mark, .rv:not(.in) .ld-read + .ld-mean { animation:none !important; }
/* 1. verdict: the banner drops in (the spoon number counts up in JS) */
.ld-vban { animation:ld-ban .6s cubic-bezier(.2,.8,.2,1) both; }
@keyframes ld-ban { from { transform:translateY(-100%); opacity:0; } }
/* 2. the three things arrive in reading order */
.ld-3 > div { animation:ld-in .45s ease both; }
.ld-3 > div:nth-child(1) { animation-delay:.25s; } .ld-3 > div:nth-child(2) { animation-delay:.5s; } .ld-3 > div:nth-child(3) { animation-delay:.75s; }
/* 3. sugar names get marked one by one, like a highlighter */
.ld-ing mark { background:linear-gradient(var(--sugar),var(--sugar)) no-repeat 0 50% / 0% 100%; animation:ld-mark .45s ease-out forwards; animation-delay:1.9s; }
@keyframes ld-mark { to { background-size:100% 100%; } }
.ld-ing mark:nth-of-type(1) { animation-delay:0.30s; } .ld-ing mark:nth-of-type(2) { animation-delay:0.55s; } .ld-ing mark:nth-of-type(3) { animation-delay:0.80s; } .ld-ing mark:nth-of-type(4) { animation-delay:1.05s; } .ld-ing mark:nth-of-type(5) { animation-delay:1.30s; } .ld-ing mark:nth-of-type(6) { animation-delay:1.55s; } .ld-ing mark:nth-of-type(7) { animation-delay:1.80s; } 
/* 4. the AI's reading ticks in row by row, then the summary */
.ld-read tr { animation:ld-row .32s ease-out both; }
@keyframes ld-row { from { opacity:0; transform:translateX(-12px); } }
.ld-read .ok, .ld-read .no { display:inline-block; animation:ld-pop .35s cubic-bezier(.3,1.5,.6,1) both; }
.ld-read tr:nth-child(2) { animation-delay:0.25s; } .ld-read tr:nth-child(2) .ok, .ld-read tr:nth-child(2) .no { animation-delay:0.42s; }
.ld-read tr:nth-child(3) { animation-delay:0.45s; } .ld-read tr:nth-child(3) .ok, .ld-read tr:nth-child(3) .no { animation-delay:0.62s; }
.ld-read tr:nth-child(4) { animation-delay:0.65s; } .ld-read tr:nth-child(4) .ok, .ld-read tr:nth-child(4) .no { animation-delay:0.82s; }
.ld-read tr:nth-child(5) { animation-delay:0.85s; } .ld-read tr:nth-child(5) .ok, .ld-read tr:nth-child(5) .no { animation-delay:1.02s; }
.ld-read tr:nth-child(6) { animation-delay:1.05s; } .ld-read tr:nth-child(6) .ok, .ld-read tr:nth-child(6) .no { animation-delay:1.22s; }
.ld-read tr:nth-child(7) { animation-delay:1.25s; } .ld-read tr:nth-child(7) .ok, .ld-read tr:nth-child(7) .no { animation-delay:1.42s; }
.ld-read tr:nth-child(8) { animation-delay:1.45s; } .ld-read tr:nth-child(8) .ok, .ld-read tr:nth-child(8) .no { animation-delay:1.62s; }
.ld-read tr:nth-child(9) { animation-delay:1.65s; } .ld-read tr:nth-child(9) .ok, .ld-read tr:nth-child(9) .no { animation-delay:1.82s; }
.ld-read tr:nth-child(10) { animation-delay:1.85s; } .ld-read tr:nth-child(10) .ok, .ld-read tr:nth-child(10) .no { animation-delay:2.02s; }
.ld-read + .ld-mean { animation:ld-in .45s ease both; animation-delay:2.2s; }
@media (prefers-reduced-motion: reduce) { .rv { opacity:1; transform:none; transition:none; } .ld-ing mark { background-size:100% 100%; } }
/* motion: rotating claim in the headline, live decode strip */
.ld-rot, .ld-rot2 { display:inline-block; transition:opacity .28s ease, transform .28s ease; }
.ld-rot.out, .ld-rot2.out { opacity:0; transform:translateY(10px); }
.ld-live { position:relative; display:grid; grid-template-columns:auto 74px 1fr auto; gap:16px; align-items:center; background:#fff; border:1px solid #c7d2fe;
  border-radius:18px; padding:14px 18px 18px; margin:-4px 0 18px; overflow:hidden; cursor:pointer; box-shadow:0 10px 26px rgba(15,23,42,.07); }
.ld-live .tag { font:800 11px 'Inter',sans-serif; letter-spacing:.07em; text-transform:uppercase; color:var(--brand); writing-mode:vertical-rl; transform:rotate(180deg); }
.ld-live .tag::before { content:""; display:inline-block; width:8px; height:8px; border-radius:50%; background:var(--red); margin-bottom:6px; animation:ld-blink 3s ease-in-out infinite; }
@keyframes ld-blink { 50% { opacity:.45; } }
.ld-live .im { width:74px; height:74px; display:grid; place-items:center; background:#f1f5f9; border-radius:12px; color:var(--faint); font-size:30px; }
.ld-live .im img { max-width:66px; max-height:66px; object-fit:contain; }
.ld-live .nm { font:800 19px 'Outfit',sans-serif; color:var(--ink); }
.ld-live .ln { font-size:14.5px; color:var(--muted); margin-top:2px; }
.ld-live .rt { text-align:right; }
.ld-live .rt .n { font:800 30px 'Outfit',sans-serif; color:var(--ink); line-height:1; }
.ld-live .rt .n small { font:600 13px 'Inter',sans-serif; color:var(--muted); }
.ld-live .rt .ld-cubes { justify-content:flex-end; margin:8px 0 0; gap:5px; }
.ld-live .rt .ld-cube { width:22px; height:22px; border-radius:6px; box-shadow:inset -3px -3px 0 #cbd5e1; }
.ld-live .body { display:contents; }
.ld-live.swap .im, .ld-live.swap .mid, .ld-live.swap .rt { opacity:0; }
.ld-live .im, .ld-live .mid, .ld-live .rt { transition:opacity .4s ease; }
.ld-live .ld-cube { animation:none; }
.ld-live .dots { position:absolute; left:0; right:0; bottom:7px; display:flex; justify-content:center; gap:5px; }
.ld-live .dots i { width:6px; height:6px; border-radius:999px; background:#cbd5e1; transition:width .3s ease, background .3s ease; }
.ld-live .dots i.on { width:18px; background:var(--brand); }
.ld-hrow.wide { grid-template-columns:minmax(150px,52%) 1fr 34px; }
.ld-hrow.wide .n { white-space:normal; }
@media (prefers-reduced-motion: reduce) { .ld-live .tag::before, .ld-marq div { animation:none; } }
body { margin:0; }
.ld-page { max-width:1080px; margin:0 auto; padding:10px 16px 48px; }
@media (max-width: 720px) {
  .ld-grid4 { grid-template-columns:repeat(2,1fr); }
  .ld-cmp-grid, .ld-field { grid-template-columns:1fr; flex-direction:column; align-items:stretch; }
  .ld-cmp-grid { display:grid; }
  .ld-tabs { flex-wrap:nowrap; overflow-x:auto; width:auto; border-radius:999px; scrollbar-width:none; -webkit-overflow-scrolling:touch; }
  .ld-tabs::-webkit-scrollbar { display:none; }
  .ld-tabs button { white-space:nowrap; flex:none; }
  .ld-nav .links a:not(.cta) { display:none; }
  .ld-nav .logo, .ld-nav a.cta { white-space:nowrap; }
  .ld-nav { padding:8px 10px; gap:8px; } .ld-nav .links { gap:6px; }
  .ld-nav .logo { font-size:15px; gap:7px; } .ld-nav .logo i { width:30px; height:30px; font-size:16px; }
  .ld-nav a.cta { font-size:0; padding:7px 11px; } .ld-nav a.cta::after { content:"By Om Rana"; font-size:12.5px; }
  .ld-lang { font-size:12px; padding:6px 9px; }
  .ld-rot, .ld-rot2 { display:block; }
  .ld-live { grid-template-columns:60px 1fr; gap:12px; } .ld-live .tag { display:none; }
  .ld-live .im { width:60px; height:60px; } .ld-live .rt { grid-column:1 / -1; text-align:left; display:flex; align-items:center; gap:12px; }
  .ld-live .rt .ld-cubes { justify-content:flex-start; margin:0; }
}
</style>
"""

JS = """
<script>
const D = JSON.parse(document.getElementById('ld-data').textContent);
const $ = s => document.querySelector(s);

// tabs
document.querySelectorAll('.ld-tabs button').forEach(b => b.onclick = () => {
  document.querySelectorAll('.ld-tabs button').forEach(x => x.classList.toggle('on', x === b));
  document.querySelectorAll('.ld-panel').forEach(p => p.classList.toggle('on', p.id === b.dataset.p));
});

// the usual suspects
function pick(code, scroll) {
  document.querySelectorAll('.ld-pc').forEach(c => {
    const on = c.dataset.code === code;
    c.classList.toggle('on', on);
    c.querySelector('.go').textContent = on ? 'Showing ↓' : 'Check this pack';
  });
  $('#res-pop').innerHTML = D.packs[code].html;
  if (scroll) $('#res-pop').scrollIntoView({behavior: 'smooth', block: 'start'});
}
document.querySelectorAll('.ld-pc').forEach(c => c.onclick = () => pick(c.dataset.code, true));
pick(D.featured[0], false);

// barcode
function lookup() {
  const code = $('#bc').value.replace(/\\D/g, '');
  if (!code) return;
  if (D.packs[code]) { $('#bc-msg').innerHTML = ''; $('#res-bc').innerHTML = D.packs[code].html; return; }
  $('#res-bc').innerHTML = '';
  $('#bc-msg').innerHTML = '<div class="ld-empty"><b>That barcode is not one of the 100 packs on this page.</b><br>' +
    'Try one of the barcodes below, or pick a pack from “The full lineup”.</div>';
}
$('#bc-go').onclick = lookup;
$('#bc').addEventListener('keydown', e => { if (e.key === 'Enter') lookup(); });
document.querySelectorAll('#bc-try button').forEach(b => b.onclick = () => { $('#bc').value = b.dataset.code; lookup(); });

// watch the AI read
function replay(code) {
  document.querySelectorAll('#rp-chips button').forEach(b => b.classList.toggle('on', b.dataset.code === code));
  $('#res-ai').innerHTML = D.replays[code];
}
document.querySelectorAll('#rp-chips button').forEach(b => b.onclick = () => replay(b.dataset.code));
replay(document.querySelector('#rp-chips button').dataset.code);

// face-off
function faceoff() {
  const a = $('#ca').value, b = $('#cb').value;
  const ta = D.packs[a].tsp, tb = D.packs[b].tsp;
  let win = null;
  if (ta !== null && tb !== null && ta !== tb) win = ta < tb ? a : b;
  const card = c => D.packs[c].cmp.replace('<div class=win>&nbsp;</div>',
      c === win ? '<div class=win><em class="ld-ic ld-ic-medal"></em> Less sugar</div>' : '<div class=win>&nbsp;</div>')
    .replace('<div class="ld-cmp">', '<div class="ld-cmp' + (win ? (c === win ? ' win' : ' lose') : '') + '">');
  $('#cmp').innerHTML = card(a) + card(b);
  const lo = Math.min(ta, tb), hi = Math.max(ta, tb);
  $('#cmp-line').innerHTML = (win && lo > 0)
    ? '<div class="ld-card" style="text-align:center;font-size:17px"><em class="ld-ic ld-ic-medal"></em> <b>' + D.packs[win].name + '</b> wins: <b>' +
      (hi / lo).toFixed(1) + '× less sugar</b> per serve.</div>' : '';
}
$('#ca').onchange = faceoff; $('#cb').onchange = faceoff; faceoff();

// full lineup
function lineup() { $('#res-all').innerHTML = D.packs[$('#sel').value].html; }
$('#sel').onchange = lineup; lineup();

// language: the plain-words lines exist in English and Hindi; the button flips which one shows
const langBtn = $('#ld-lang');
function setLang(hi) {
  document.body.classList.toggle('lang-hi', hi);
  if (langBtn) langBtn.textContent = hi ? 'English' : 'हिंदी';
  try { localStorage.setItem('ld-lang', hi ? 'hi' : 'en'); } catch (e) {}
}
if (langBtn) {
  langBtn.onclick = () => setLang(!document.body.classList.contains('lang-hi'));
  try { if (localStorage.getItem('ld-lang') === 'hi') setLang(true); } catch (e) {}
}

// ---- motion ----
const calm = matchMedia('(prefers-reduced-motion: reduce)').matches;

// 1. the headline changes as a pair: the claim on the front, and what that claim hides on the back
const rot = $('.ld-rot'), rot2 = $('.ld-rot2');
const pairs = [['Healthy', 'Sugar'], ['Multigrain', 'Maida'], ['High protein', 'A tiny serve'], ['No added sugar', 'Fruit syrup']];
let ci = 0;
function nextPair() {
  rot.classList.add('out'); rot2.classList.add('out');
  setTimeout(() => {
    ci = (ci + 1) % pairs.length;
    rot.textContent = pairs[ci][0]; rot2.textContent = pairs[ci][1];
    rot.classList.remove('out'); rot2.classList.remove('out');
  }, 280);
}

// 2. live strip: one pack at a time; click it to open that pack; hovering holds it still
const live = $('#ld-live');
let li = -1, liveHeld = false;
function showLive() {
  li = (li + 1) % D.show.length;
  const s = D.show[li];
  live.classList.add('swap');
  setTimeout(() => {
    live.querySelector('.im').innerHTML = s.img ? '<img src="' + s.img + '" alt="">' : '<em class="ld-ic ld-ic-package"></em>';
    live.querySelector('.nm').innerHTML = s.name + ' <span class="ld-chip ' + s.color + '">' + s.word + '</span>';
    live.querySelector('.ln').innerHTML = s.line;
    const full = Math.floor(s.tsp), part = s.tsp - full;
    let cubes = '<div class="ld-cube"></div>'.repeat(Math.min(full, 10));
    if (part >= 0.1 && full < 10) cubes += '<div class="ld-cube part" style="--empty:' + Math.round((1 - part) * 100) + '%"></div>';
    live.querySelector('.rt').innerHTML = '<div class="n">' + s.tsp.toFixed(1) + ' <small>spoons of sugar per serve</small></div><div class="ld-cubes">' + cubes + '</div>';
    live.dataset.code = s.code;
    live.querySelectorAll('.dots i').forEach((d, k) => d.classList.toggle('on', k === li));
    live.classList.remove('swap');
  }, 420);
}
if (live) {
  live.querySelector('.dots').innerHTML = '<i></i>'.repeat(D.show.length);
  showLive();
  live.onmouseenter = () => { liveHeld = true; };
  live.onmouseleave = () => { liveHeld = false; };
  live.onclick = () => {
    document.querySelector('[data-p="p-pop"]').click();
    const code = live.dataset.code;
    if (document.querySelector('.ld-pc[data-code="' + code + '"]')) pick(code, true);
  };
}

// one clock: the headline moves every BEAT, the strip every second beat, so the two never change out of step
const BEAT = 3000;
let beat = 0;
if (!calm) setInterval(() => {
  beat++;
  if (rot && rot2) nextPair();
  if (live && !liveHeld && beat % 2 === 0) showLive();
}, BEAT);

// 3. numbers count up the first time they scroll into view
function countUp(el) {
  const node = el.firstChild;
  if (!node || node.nodeType !== 3) return;
  const m = node.textContent.match(/^(\\d+)(.*)$/);
  if (!m || / in /.test(node.textContent)) return;
  const end = +m[1], tail = m[2], t0 = performance.now();
  (function step(t) {
    const k = Math.max(0, Math.min((t - t0) / 900, 1));   // rAF time can start a hair before t0
    node.textContent = Math.round(end * (1 - Math.pow(1 - k, 3))) + tail;
    if (k < 1) setTimeout(() => step(performance.now()), 30);   // a timer, so it finishes even in a background tab
  })(t0);
}
if (!calm && 'IntersectionObserver' in window) {
  const io = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) { countUp(e.target); io.unobserve(e.target); } }), {threshold: .6});
  document.querySelectorAll('.ld-stat b, .ld-kpi b, .ld-donut').forEach(el => io.observe(el));
}
// ---- scroll reveal ----
// Cards are hidden until they scroll into view; the animations inside each card start at that moment, once.
// No IntersectionObserver: a plain position check is easier to reason about and works the same everywhere.
const RV = '.ld-card, .ld-intro, .ld-kpi, .ld-pc, .ld-lead, .ld-cmp, .ld-empty';
function countTo(el) {                                   // "3.2" counts up from 0.0 when the banner appears
  const end = parseFloat(el.textContent);
  if (isNaN(end)) return;
  const t0 = performance.now();
  (function step(t) {
    const k = Math.max(0, Math.min((t - t0) / 900, 1));
    el.textContent = (end * (1 - Math.pow(1 - k, 3))).toFixed(1);
    if (k < 1) setTimeout(() => step(performance.now()), 30);   // a timer, so it finishes even in a background tab
  })(t0);
}
function tagNew() {                                      // mark any card that was just added to the page
  document.querySelectorAll(RV).forEach(el => {
    if (el.classList.contains('rv') || el.closest('.ld-live')) return;
    el.classList.add('rv');
    const sibs = [...el.parentElement.children].filter(x => x.matches('.ld-pc, .ld-kpi'));
    const i = sibs.indexOf(el);
    if (i > 0) { el.style.transitionDelay = (i % 4) * 70 + 'ms'; setTimeout(() => { el.style.transitionDelay = ''; }, 1200); }
  });
}
function showInView() {
  const h = window.innerHeight || document.documentElement.clientHeight;
  document.querySelectorAll('.rv:not(.in)').forEach(el => {
    if (!el.offsetParent) return;                        // inside a closed tab
    const r = el.getBoundingClientRect();
    if (r.top < h * 0.92 && r.bottom > 0) {
      el.classList.add('in');
      const n = el.querySelector('.ld-vban .s b');
      if (n) countTo(n);
    }
  });
  const bar = document.getElementById('ld-sp');
  if (bar) {
    const max = document.documentElement.scrollHeight - h;
    bar.style.width = (max > 0 ? Math.min(100, 100 * window.scrollY / max) : 0) + '%';
  }
}
if (!calm) {
  const bar = document.createElement('div'); bar.className = 'ld-sp'; bar.id = 'ld-sp'; document.body.appendChild(bar);
  tagNew(); showInView();
  let queued = false;
  // a timer, not requestAnimationFrame: frames pause in background tabs and the cards would stay hidden
  const later = () => { if (!queued) { queued = true; setTimeout(() => { queued = false; showInView(); }, 40); } };
  window.addEventListener('scroll', later, {passive: true});
  window.addEventListener('resize', later);
  setInterval(showInView, 300);          // safety net: some browsers hold back scroll events while a tab is in the background
  // picking a pack, a barcode, a face-off or a tab swaps content in: tag it before it paints, then check
  new MutationObserver(() => { tagNew(); later(); }).observe(document.querySelector('.ld-page'), {childList: true, subtree: true});
  document.querySelectorAll('.ld-tabs button').forEach(b => b.addEventListener('click', later));
}
// ---- sliding tab pill ----
// One dark pill sits behind the active tab and slides when another tab is clicked (also right after fonts load or a resize).
const tabsEl = document.querySelector('.ld-tabs');
if (tabsEl) {
  const pill = document.createElement('span');
  pill.className = 'ld-pill still';
  tabsEl.prepend(pill);
  tabsEl.classList.add('has-pill');
  const movePill = () => {
    const b = tabsEl.querySelector('button.on');
    if (!b) return;
    pill.style.left = b.offsetLeft + 'px'; pill.style.top = b.offsetTop + 'px';
    pill.style.width = b.offsetWidth + 'px'; pill.style.height = b.offsetHeight + 'px';
  };
  movePill();
  setTimeout(() => pill.classList.remove('still'), 60);
  tabsEl.querySelectorAll('button').forEach(b => b.addEventListener('click', () => {
    movePill();
    if (tabsEl.scrollWidth > tabsEl.clientWidth) tabsEl.scrollLeft = b.offsetLeft - (tabsEl.clientWidth - b.offsetWidth) / 2;   // phones: keep the active tab in view
  }));
  window.addEventListener('resize', movePill);
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(movePill);
  setTimeout(movePill, 600);
}
</script>
"""


def main() -> None:
    rows = [json.loads(line) for line in (ROOT / "eval" / "data" / "testset.jsonl").open(encoding="utf-8")]
    all_sugar = [float(v) for r in rows if (v := (r["label"].get("per_100") or {}).get("total_sugars_g")) is not None]

    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "share").mkdir(parents=True)

    packs, names = {}, {}
    for r in rows:
        code, label = r["barcode"], r["label"]
        img = (r.get("image_urls") or {}).get("front")
        result = decode_label(label)
        lights = ui._lights(label.get("per_100") or {}, result["product"]["is_liquid"])
        name = ui.full_name(label.get("brand"), label.get("product_name"))
        names[code] = name
        packs[code] = {
            "name": ui.esc(name),
            "tsp": result["sugar"]["teaspoons_total_per_serve"],
            "html": result_html(label, result, img, all_sugar, code),
            "cmp": ui.compare_card(label, result, img, lights, winner=False),
        }
        (OUT / "share" / f"{code}.png").write_bytes(ui.share_image(label, result, lights))

    # featured cards with the same ribbons as the app
    feat = [c for c in FEATURED if c in packs]
    sugar = {c: (next(r for r in rows if r["barcode"] == c)["label"].get("per_100") or {}).get("total_sugars_g") for c in feat}
    sev = {c: decode_label(next(r for r in rows if r["barcode"] == c)["label"])["severity_score"] for c in feat}
    ribbons = {}
    with_sugar = [c for c in feat if sugar[c] is not None]
    if with_sugar:
        ribbons[max(with_sugar, key=lambda c: sugar[c])] = "MOST SUGAR"
        ribbons.setdefault(min(with_sugar, key=lambda c: sugar[c]), "LEAST SUGAR")
    ribbons.setdefault(max(feat, key=lambda c: sev[c]), "BIGGEST TRICK")
    cards = ""
    for c in feat:
        r = next(r for r in rows if r["barcode"] == c)
        liquid = decode_label(r["label"])["product"]["is_liquid"]
        cards += (f'<div class="ld-pc" data-code="{c}">'
                  + ui.product_card(r["label"].get("brand"), r["label"].get("product_name"),
                                    (r.get("image_urls") or {}).get("front"), sugar[c], liquid, ribbon=ribbons.get(c))
                  + '<div class="go">Check this pack</div></div>')

    order = sorted(packs, key=lambda c: names[c].lower())
    options = lambda sel: "".join(f'<option value="{c}"{" selected" if c == sel else ""}>{ui.esc(names[c])}</option>'
                                  for c in order)

    by_code = {r["barcode"]: r for r in rows}
    dash = ui.dashboard([(r["label"], decode_label(r["label"])) for r in rows])
    rp_chips, rp_html = replays(by_code, all_sugar)
    try_codes = "".join(f'<button data-code="{c}">{c} · {ui.esc(names[c])}</button>'
                        for c in ("8901719125478", "8901058006292", "8906059638329"))

    tabs = [("p-pop", "The usual suspects"), ("p-dash", "The big picture"), ("p-cmp", "Face-off"),
            ("p-ai", "Watch the AI read"), ("p-bc", "Scan a barcode"), ("p-all", "The full lineup")]
    tab_bar = '<div class="ld-tabs" id="packs">' + "".join(
        f'<button data-p="{p}"{" class=on" if i == 0 else ""}>{t}</button>' for i, (p, t) in enumerate(tabs)) + "</div>"

    panels = (
        f'<div class="ld-panel on" id="p-pop">{ui.intro("suspects")}<div class="ld-grid4">{cards}</div><div id="res-pop"></div></div>'
        f'<div class="ld-panel" id="p-bc">{ui.intro("barcode")}'
        f'<div class="ld-field"><div><label for="bc">Type the 13 digits printed under the black bars (Indian packs start with 890)</label>'
        f'<input id="bc" inputmode="numeric" placeholder="e.g. 8901719125478  (Parle-G gold)"></div>'
        f'<button class="ld-btn" id="bc-go">Check it</button></div>'
        f'<div class="ld-chips" id="bc-try">{try_codes}</div><div id="bc-msg" class="ld-msg"></div><div id="res-bc"></div></div>'
        f'<div class="ld-panel" id="p-dash">{ui.intro("bigpicture")}{dash}</div>'
        f'<div class="ld-panel" id="p-ai">{ui.intro("airead")}{rp_chips}<div id="res-ai"></div>{own_photo_card()}</div>'
        f'<div class="ld-panel" id="p-cmp">{ui.intro("faceoff")}'
        f'<div class="ld-cmp-grid ld-field" style="display:grid"><div><label for="ca">Pack A</label><select id="ca">{options("8906059638329")}</select></div>'
        f'<div><label for="cb">Pack B</label><select id="cb">{options("8901648026167")}</select></div></div>'
        f'<div class="ld-cmp-grid" id="cmp"></div><div id="cmp-line"></div></div>'
        f'<div class="ld-panel" id="p-all">{ui.intro("lineup")}'
        f'<div class="ld-field"><div><label for="sel">Pick any of the 100 packs we checked</label><select id="sel">{options(FEATURED[0])}</select></div></div>'
        f'<div id="res-all"></div></div>'
    )

    # the live strip under the hero: one line per featured pack, taken from the same verdict logic as the cards
    show = []
    for c in feat:
        label, result = by_code[c]["label"], decode_label(by_code[c]["label"])
        lights = ui._lights(label.get("per_100") or {}, result["product"]["is_liquid"])
        color, word = ui.verdict(result, lights)
        headline, _ = ui._reasons(result, lights, "ml" if result["product"]["is_liquid"] else "g")
        tsp = result["sugar"]["teaspoons_total_per_serve"]
        if tsp is not None:
            show.append({"code": c, "name": ui.esc(names[c]), "img": (by_code[c].get("image_urls") or {}).get("front"),
                         "tsp": round(tsp, 1), "color": color, "word": word, "line": ui.esc(headline)})
    live_strip = ('<div class="ld-live" id="ld-live" title="Click to open this pack"><div class="tag">Decoding now</div>'
                  '<div class="im"></div><div class="mid"><div class="nm"></div><div class="ln"></div></div><div class="rt"></div>'
                  '<div class="dots"></div></div>')

    data = json.dumps({"packs": packs, "featured": feat, "replays": rp_html, "show": show}, ensure_ascii=False).replace("</", "<\\/")
    page = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>Label Decoder</title>'
        '<meta name="description" content="Healthy on the front, sugar on the back. Decode 100 Indian food labels: sugar in spoons, hidden sugar names, claims checked against FSSAI rules.">'
        '<meta property="og:title" content="Label Decoder: healthy on the front, sugar on the back">'
        '<meta property="og:description" content="Sugar in spoons, hidden sugar names and every pack claim checked against Indian food law. 100 Indian packs.">'
        f'<meta property="og:type" content="website"><meta property="og:url" content="{SITE}/">'
        f'<meta property="og:image" content="{SITE}/og.png"><meta property="og:image:width" content="1200">'
        '<meta property="og:image:height" content="630"><meta name="twitter:card" content="summary_large_image">'
        f'<meta name="twitter:image" content="{SITE}/og.png"><link rel="canonical" href="{SITE}/">'
        '<link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🔍</text></svg>">'
        + ui.CSS + EXTRA_CSS +
        '</head><body class="stApp"><div class="ld-page">'
        + '<div class="ld-scribble l" style="top:150px" aria-hidden="true">the front sells.<br>the back tells.<svg width="78" height="42" viewBox="0 0 78 42" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 34c16-24 40-30 64-16"/><path d="M56 8l13 9l-13 9"/></svg></div><div class="ld-scribble r" style="top:470px" aria-hidden="true"><svg width="78" height="42" viewBox="0 0 78 42" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M74 6c-20 26-44 30-66 14"/><path d="M20 30l-13-10l14-7"/></svg>always turn<br>the pack over.</div>'
        + ui.navbar(GITHUB, LIVE, lang_toggle=True) + ui.hero(cta=True) + live_strip + ui.about()
        + tab_bar + panels + ui.method() + ui.footer(GITHUB)
        + f'</div><script type="application/json" id="ld-data">{data}</script>' + JS + '</body></html>'
    )
    (OUT / "og.png").write_bytes(og_image())
    (OUT / "index.html").write_text(page, encoding="utf-8")
    size = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file())
    print(f"wrote {OUT} : {len(packs)} packs, {len(list((OUT / 'share').iterdir()))} share cards, {size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
