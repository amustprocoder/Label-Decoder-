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
from src.replays import replay_cards  # noqa: E402

OUT = ROOT / "site"
GITHUB = "https://github.com/amustprocoder/Label-Decoder-"
SITE = "https://labeldecoder-omrana.netlify.app"   # where this folder is deployed; link previews need the full URL
LIVE = None       # URL of the Streamlit app once it is deployed; None keeps the site free of dead links
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
    return (ui.top_card(label, result, img, lights) + ui.health_card(result) + ui.three_things(result, lights)
            + ui.sugar_cards(result)
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
    """Chip bar + {barcode: html} for the recorded photo readings (the cards come from src/replays.py)."""
    chips, html = "", {}
    for i, (code, name, tag, miss, card) in enumerate(replay_cards(rows)):
        html[code] = card
        chips += (f'<button data-code="{code}"{" class=on" if i == 0 else ""}>{ui.esc(name)}'
                  f'<i class="{"miss" if miss else ""}">{ui.esc(tag)}</i></button>')
    return f'<div class="ld-chips" id="rp-chips">{chips}</div>', html


EXTRA_CSS = ui.SITE_CSS   # the site-only look now lives in src/ui.py, shared with the Streamlit app

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
        '<title>Label Decoder: is this pack healthy?</title>'
        '<meta name="description" content="Is this pack healthy or not? Label Decoder reads the ingredient list and nutrition table on the back of Indian food packs and gives one verdict from four checks. 100 packs checked.">'
        '<meta property="og:title" content="Label Decoder: is this pack healthy or not?">'
        '<meta property="og:description" content="Reads the ingredient list and nutrition table on the back of the pack. Four checks, one answer: healthy or not healthy. 100 Indian packs.">'
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
