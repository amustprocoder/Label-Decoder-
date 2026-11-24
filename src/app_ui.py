"""
Streamlit-only presentation: what the website does with its own page script, done here for the app.

The look is shared with the website (src/ui.py: CSS and SITE_CSS). This module adds what Streamlit needs on top:

  APP_CSS   restyles Streamlit's own widgets (tabs, bordered containers, uploader, alerts) to the site's design.
            Written against Streamlit 1.61 markup (react-aria tabs, bordered st.container = the stVerticalBlock itself).
  app_js()  the website's motion layer (rotating headline, "Decoding now" strip, scroll reveal, count-ups, sliding
            tab pill, Hindi toggle) adapted to Streamlit, where the page scrolls inside <section class="stMain">
            and content is re-rendered on every click. Injected with st.html(..., unsafe_allow_javascript=True).
  builders  the live strip shell and its items, the margin notes, the sample-pack card, the replay panel, and the
            "what the AI read" card for a live photo or text read.
"""

from __future__ import annotations

import json
import re

from src import ui
from src.ui import READ_FIELDS, esc, fmt

APP_CSS = """
<style>
/* ===== Streamlit chrome: none of it shows; the page column is the site's 1080 px column ===== */
header[data-testid="stHeader"], [data-testid="stStatusWidget"], [data-testid="stAppDeployButton"] { display:none !important; }
.stMainBlockContainer { position:relative; max-width:1112px !important; padding:14px 16px 48px !important; box-sizing:border-box; }
/* the site collapses card margins; a flex column cannot, so each HTML block drops its outer margins and the column gap spaces them */
[data-testid="stVerticalBlock"] { gap:14px; }
.stHtml > :first-child { margin-top:0 !important; } .stHtml > :last-child { margin-bottom:0 !important; }
.stHtml > #how { margin-top:12px !important; }
/* top bar: the element container sticks (it sits in the page column), the bar inside it stays put */
.stElementContainer:has(> .stHtml > .ld-nav) { position:sticky; top:0; z-index:60; }
.stApp .ld-nav { position:static; margin:0; }
/* handwritten margin notes: beside the hero, only where there is real margin */
.stApp .ld-scribble { top:90px; } .stApp .ld-scribble.r { top:410px; }
@media (max-width: 1519px) { .stApp .ld-scribble { display:none !important; } }

/* ===== tabs (react-aria markup): the same white pill bar as the site, with the sliding dark pill ===== */
[data-testid="stTabs"] [role="tablist"] { position:relative; display:flex; flex-wrap:wrap; gap:6px; background:#fff; border:1px solid var(--line) !important;
  border-radius:999px; padding:5px; width:fit-content; max-width:100%; margin:6px 0 2px; box-shadow:none; }
[data-testid="stTab"] { position:relative; z-index:1; padding:8px 16px !important; margin:0 !important; border-radius:999px; color:var(--muted);
  background:transparent; transition:all .15s; cursor:pointer; }
[data-testid="stTab"] p { font:600 14.5px 'Inter',sans-serif !important; color:inherit !important; margin:0; }
[data-testid="stTab"]:hover { background:#fafaf9; color:var(--ink); }
[data-testid="stTab"][aria-selected="true"] { color:#fff; background:linear-gradient(135deg,#334155,#0f172a); box-shadow:0 4px 12px rgba(15,23,42,.3); }
[role="tablist"].has-pill [data-testid="stTab"][aria-selected="true"] { background:transparent; box-shadow:none; }
[data-testid="stTabs"] .react-aria-SelectionIndicator { display:none !important; }
[data-testid="stTabPanel"] { padding-top:18px !important; animation:ld-tabin .34s ease both; }
@media (max-width: 720px) {
  [data-testid="stTabs"] [role="tablist"] { flex-wrap:nowrap; overflow-x:auto; width:auto; scrollbar-width:none; }
  [data-testid="stTab"] { white-space:nowrap; flex:none; }
}

/* ===== product cards: the bordered container is the card (see also the picker rules in ui.CSS) ===== */
[data-testid="stVerticalBlock"]:has(> .stElementContainer > .stHtml > .ld-pcard) { transition:opacity .6s ease, transform .22s ease, box-shadow .18s; }
[data-testid="stVerticalBlock"]:has(> .stElementContainer > .stHtml > .ld-pcard).rv.in:hover { transform:translateY(-3px); }
[data-testid="stVerticalBlock"]:has(> .stElementContainer > .stHtml > .ld-pcard) .stButton button { font-weight:700; font-size:14px; padding:8px; min-height:0; }

/* ===== Streamlit widgets in the site's clothes ===== */
[data-testid="stFileUploaderDropzone"] { border:2px dashed #a5b4fc !important; border-radius:18px !important; background:#fff !important; }
[data-testid="stAlert"], [data-testid="stAlertContainer"] { border-radius:14px; }
[data-testid="stAlert"] p { font-size:14.5px; }
[data-testid="stExpander"] details { border:1px solid var(--line) !important; border-radius:14px !important; background:#fff; }
[data-testid="stExpander"] summary p { font-weight:700; color:var(--ink); }
[data-testid="stCaptionContainer"] p { font-size:13.5px; color:var(--faint); }
[data-testid="stSpinner"] { font-weight:600; color:var(--ink); }
[data-testid="stWidgetLabel"] p { font-size:14px; color:var(--muted); }
/* what the AI read: the facts beside the numbers table */
.ld-facts { display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:12px; }
.ld-facts > div { background:#fafaf9; border:1px solid var(--line); border-radius:12px; padding:10px 12px; font-size:14px; color:var(--muted); line-height:1.5; }
.ld-facts > div > b { display:block; font-size:11px; letter-spacing:.06em; text-transform:uppercase; color:var(--faint); margin-bottom:3px; }
.ld-facts > div.wide { grid-column:1 / -1; }
@media (max-width: 720px) { .ld-facts { grid-template-columns:1fr; } }
</style>
"""

APP_JS = """
(() => {
  const $ = s => document.querySelector(s);
  const D = __LD_DATA__;                           // inlined by app_js(): Streamlit lifts <script> tags out of the HTML, so a JSON tag is not there to read
  const SC = $('section.stMain') || document.scrollingElement;   // Streamlit scrolls this section, not the window
  const calm = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const STEP = 300;

  if (window.__ldApp) { window.__ldApp.data = D; window.__ldApp.refresh(); return; }   // a rerun ran this again: keep one clock
  const A = window.__ldApp = {data: D};

  // in-page links: "#packs" is the tab bar, "#how" the method card; scroll the section instead of changing the URL
  document.addEventListener('click', e => {
    const a = e.target.closest('a[href^="#"]');
    if (!a) return;
    const id = a.getAttribute('href').slice(1);
    const el = id === 'packs' ? $('[data-testid="stTabs"]') : document.getElementById(id);
    if (!el) return;
    e.preventDefault();
    el.scrollIntoView({behavior: calm ? 'auto' : 'smooth', block: 'start'});
  });

  // language: the plain-words lines exist in English and Hindi; the button flips which one shows
  function setLang(hi) {
    document.body.classList.toggle('lang-hi', hi);
    const b = $('#ld-lang');
    if (b) b.textContent = hi ? 'English' : 'हिंदी';
    try { localStorage.setItem('ld-lang', hi ? 'hi' : 'en'); } catch (e) {}
  }
  document.addEventListener('click', e => { if (e.target.closest('#ld-lang')) setLang(!document.body.classList.contains('lang-hi')); });
  try { if (localStorage.getItem('ld-lang') === 'hi') setLang(true); } catch (e) {}

  // 1. the headline changes as a pair: the claim on the front, and what that claim hides on the back
  const pairs = [['Healthy', 'Sugar'], ['Multigrain', 'Maida'], ['High protein', 'A tiny serve'], ['No added sugar', 'Fruit syrup']];
  let ci = 0;
  function nextPair() {
    const rot = $('.ld-rot'), rot2 = $('.ld-rot2');
    if (!rot || !rot2) return;
    rot.classList.add('out'); rot2.classList.add('out');
    setTimeout(() => {
      ci = (ci + 1) % pairs.length;
      rot.textContent = pairs[ci][0]; rot2.textContent = pairs[ci][1];
      rot.classList.remove('out'); rot2.classList.remove('out');
    }, 280);
  }

  // 2. live strip: one pack at a time; hovering holds it; clicking opens that pack under "The usual suspects"
  let li = -1, liveHeld = false;
  function showLive() {
    const live = $('#ld-live'), show = A.data.show || [];
    if (!live || !show.length) return;
    if (live.querySelectorAll('.dots i').length !== show.length) live.querySelector('.dots').innerHTML = '<i></i>'.repeat(show.length);
    li = (li + 1) % show.length;
    const s = show[li];
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
  document.addEventListener('mouseover', e => { if (e.target.closest('#ld-live')) liveHeld = true; });
  document.addEventListener('mouseout', e => {
    if (e.target.closest('#ld-live') && !(e.relatedTarget && e.relatedTarget.closest('#ld-live'))) liveHeld = false;
  });
  function openPack(code) {                       // the cards under "The usual suspects" are Streamlit buttons: click the right one
    const card = document.querySelector('.ld-pcard[data-code="' + code + '"]');
    if (!card) return false;
    if (!card.classList.contains('on')) {
      const block = card.closest('[data-testid="stVerticalBlock"]');
      const btn = block && block.querySelector('button');
      if (btn) btn.click();
    }
    const tabs = $('[data-testid="stTabs"]');
    if (tabs) tabs.scrollIntoView({behavior: calm ? 'auto' : 'smooth', block: 'start'});
    return true;
  }
  document.addEventListener('click', e => {
    const live = e.target.closest('#ld-live');
    if (!live || !live.dataset.code) return;
    const first = document.querySelector('[data-testid="stTab"]');
    if (first && first.getAttribute('aria-selected') !== 'true') first.click();
    if (!openPack(live.dataset.code)) setTimeout(() => openPack(live.dataset.code), 450);
  });

  // one clock: the headline moves every BEAT, the strip every second beat, so the two never change out of step
  const BEAT = 3000;
  let beat = 0;
  showLive();
  if (!calm) setInterval(() => { beat++; nextPair(); if (!liveHeld && beat % 2 === 0) showLive(); }, BEAT);

  // 3. numbers count up the first time they scroll into view
  function countUp(el) {
    const node = el.firstChild;
    if (!node || node.nodeType !== 3) return;
    const m = node.textContent.match(/^(\\d+)(.*)$/);
    if (!m || / in /.test(node.textContent)) return;
    const end = +m[1], tail = m[2], t0 = performance.now();
    (function step(t) {
      const k = Math.max(0, Math.min((t - t0) / 900, 1));
      node.textContent = Math.round(end * (1 - Math.pow(1 - k, 3))) + tail;
      if (k < 1) setTimeout(() => step(performance.now()), 30);   // a timer, so it finishes even in a background tab
    })(t0);
  }
  const io = (!calm && 'IntersectionObserver' in window)
    ? new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) { countUp(e.target); io.unobserve(e.target); } }), {threshold: .6})
    : null;
  function watchNumbers() {
    if (!io) return;
    document.querySelectorAll('.ld-stat b, .ld-kpi b, .ld-donut').forEach(el => {
      if (!el.dataset.ldSeen) { el.dataset.ldSeen = '1'; io.observe(el); }
    });
  }

  // 4. scroll reveal: a card stays hidden until it scrolls into view, then its own animation plays once
  const RV = '.ld-card, .ld-intro, .ld-kpi, .ld-lead, .ld-cmp, .ld-empty, .ld-pcard';
  function countTo(el) {                          // "3.2" counts up from 0.0 when the banner appears
    const end = parseFloat(el.textContent);
    if (isNaN(end)) return;
    const t0 = performance.now();
    (function step(t) {
      const k = Math.max(0, Math.min((t - t0) / 900, 1));
      el.textContent = (end * (1 - Math.pow(1 - k, 3))).toFixed(1);
      if (k < 1) setTimeout(() => step(performance.now()), 30);
    })(t0);
  }
  function tagNew() {                             // mark any card that was just added to the page
    document.querySelectorAll(RV).forEach(el => {
      // a product card is a bordered Streamlit container: reveal the container, not just the HTML inside it
      const t = el.classList.contains('ld-pcard') ? (el.closest('[data-testid="stVerticalBlock"]') || el) : el;
      if (t.classList.contains('rv') || t.closest('.ld-live')) return;
      t.classList.add('rv');
      const grid = el.classList.contains('ld-pcard') ? '.ld-pcard' : el.classList.contains('ld-kpi') ? '.ld-kpi' : null;
      if (grid) {
        const i = [...document.querySelectorAll(grid)].indexOf(el);
        if (i > 0) { t.style.transitionDelay = (i % 4) * 70 + 'ms'; setTimeout(() => { t.style.transitionDelay = ''; }, 1200); }
      }
    });
  }
  function showInView() {
    const h = window.innerHeight || document.documentElement.clientHeight;
    document.querySelectorAll('.rv:not(.in)').forEach(el => {
      if (!el.offsetParent) return;               // inside a closed expander
      const r = el.getBoundingClientRect();
      if (r.top < h * 0.92 && r.bottom > 0) {
        el.classList.add('in');
        const n = el.querySelector('.ld-vban .s b');
        if (n) countTo(n);
      }
    });
    const bar = document.getElementById('ld-sp');
    if (bar) {
      const max = SC.scrollHeight - SC.clientHeight;
      bar.style.width = (max > 0 ? Math.min(100, 100 * SC.scrollTop / max) : 0) + '%';
    }
  }

  // 5. one dark pill sits behind the active tab and slides when another tab is clicked
  function movePill() {
    const list = $('[data-testid="stTabs"] [role="tablist"]');
    if (!list) return;
    let pill = list.querySelector('.ld-pill');
    if (!pill) {
      pill = document.createElement('span');
      pill.className = 'ld-pill still';
      list.appendChild(pill);
      list.classList.add('has-pill');
      setTimeout(() => pill.classList.remove('still'), 60);
    }
    const b = list.querySelector('[aria-selected="true"]');
    if (!b) return;
    pill.style.left = b.offsetLeft + 'px'; pill.style.top = b.offsetTop + 'px';
    pill.style.width = b.offsetWidth + 'px'; pill.style.height = b.offsetHeight + 'px';
  }

  A.refresh = () => {
    tagNew(); showInView(); watchNumbers(); movePill();
    const b = $('#ld-lang');
    if (b) b.textContent = document.body.classList.contains('lang-hi') ? 'English' : 'हिंदी';
  };
  if (!calm) {
    const bar = document.createElement('div'); bar.className = 'ld-sp'; bar.id = 'ld-sp'; document.body.appendChild(bar);
    let queued = false;
    const later = () => { if (!queued) { queued = true; setTimeout(() => { queued = false; showInView(); }, 40); } };
    SC.addEventListener('scroll', later, {passive: true});
    window.addEventListener('resize', () => { later(); movePill(); });
    // Streamlit swaps content in on every click: tag it before it paints, then check what is in view
    new MutationObserver(() => { tagNew(); later(); }).observe(SC, {childList: true, subtree: true});
  }
  setInterval(A.refresh, STEP);                   // safety net: tabs, expanders, background tabs, late fonts
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(movePill);
  A.refresh();
})();
"""


def _json(data) -> str:
    """JSON that is safe to inline inside a <script>: no '<' at all (see _script) and no line separators JS chokes on."""
    return (json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
            .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))


def _script(js: str) -> str:
    """Wrap page script for st.html(unsafe_allow_javascript=True). Streamlit runs the HTML through DOMPurify first, which
    silently drops any <script> whose text contains a tag-like "<x" or "</"; this code builds HTML strings, so every such
    "<" is written as the JS escape \\u003c. A "<" followed by a space (a comparison) is left alone."""
    return "<script>" + re.sub(r"<(?=[/\w!])", r"\\u003c", js) + "</script>"


def app_js(show: list[dict]) -> str:
    """The page script with its data inlined. Render once, at the end of the page, with st.html(..., unsafe_allow_javascript=True)."""
    return _script(APP_JS.replace("__LD_DATA__", _json({"show": show})))


def live_strip() -> str:
    """The "Decoding now" strip under the hero. Empty shell; app_js() fills it and rotates the packs."""
    return ('<div class="ld-live" id="ld-live" title="Click to open this pack"><div class="tag">Decoding now</div>'
            '<div class="im"></div><div class="mid"><div class="nm"></div><div class="ln"></div></div><div class="rt"></div>'
            '<div class="dots"></div></div>')


def live_item(code: str, label: dict, result: dict, img: str | None) -> dict | None:
    """One line for the strip, from the same verdict logic as the cards. None when the pack prints no sugar."""
    tsp = result["sugar"]["teaspoons_total_per_serve"]
    if tsp is None:
        return None
    liquid = result["product"]["is_liquid"]
    lights = ui._lights(label.get("per_100") or {}, liquid)
    color, word = ui.verdict(result, lights)
    headline, _ = ui._reasons(result, lights, "ml" if liquid else "g")
    return {"code": code, "name": esc(ui.full_name(label.get("brand"), label.get("product_name"))), "img": img,
            "tsp": round(tsp, 1), "color": color, "word": word, "line": esc(headline)}


def scribbles() -> str:
    """Two handwritten notes in the page margins (shown from 1520 px wide; see APP_CSS)."""
    arrow_r = ('<svg width="78" height="42" viewBox="0 0 78 42" fill="none" stroke="currentColor" stroke-width="2.2" '
               'stroke-linecap="round" stroke-linejoin="round"><path d="M4 34c16-24 40-30 64-16"/><path d="M56 8l13 9l-13 9"/></svg>')
    arrow_l = ('<svg width="78" height="42" viewBox="0 0 78 42" fill="none" stroke="currentColor" stroke-width="2.2" '
               'stroke-linecap="round" stroke-linejoin="round"><path d="M74 6c-20 26-44 30-66 14"/><path d="M20 30l-13-10l14-7"/></svg>')
    return (f'<div class="ld-scribble l" aria-hidden="true">the front sells.<br>the back tells.{arrow_r}</div>'
            f'<div class="ld-scribble r" aria-hidden="true">{arrow_l}always turn<br>the pack over.</div>')


def sample_card(name: str, img: str | None, n_photos: int) -> str:
    """A pack whose photos ship with the app, offered for a live read. Same card as the product picker."""
    pic = f'<img src="{img}" alt="">' if img else '<span style="font-size:40px;color:var(--faint)">' + ui.icon("package") + '</span>'
    return (f'<div class="ld-pcard"><div class="img">{pic}</div><div class="nm">{esc(name)}</div>'
            f'<span class="ld-chip grey">{n_photos} photos · read live</span></div>')


def replay_panel(cards: list[tuple[str, str, str, bool, str]]) -> str:
    """Chip bar + the recorded readings, swapped in by a small script (no rerun), exactly as on the website."""
    chips = "".join(f'<button data-code="{code}"{" class=on" if i == 0 else ""}>{esc(name)}'
                    f'<i class="{"miss" if miss else ""}">{esc(tag)}</i></button>'
                    for i, (code, name, tag, miss, _) in enumerate(cards))
    js = """
(() => {
  const chips = document.getElementById('rp-chips'), out = document.getElementById('res-ai');
  if (!chips || !out) return;
  const R = __LD_REPLAYS__;
  function show(code) {
    chips.querySelectorAll('button').forEach(b => b.classList.toggle('on', b.dataset.code === code));
    out.innerHTML = R[code];
    if (window.__ldApp) window.__ldApp.refresh();
  }
  chips.querySelectorAll('button').forEach(b => b.onclick = () => show(b.dataset.code));
  show(chips.querySelector('button').dataset.code);
})();
"""
    js = js.replace("__LD_REPLAYS__", _json({code: html for code, _, _, _, html in cards}))
    return f'<div class="ld-chips" id="rp-chips">{chips}</div><div id="res-ai"></div>' + _script(js)


def live_read_card(label: dict, photos: list[str], secs: float | None) -> str:
    """A live photo or text read, shown the way the site shows a recorded one: the photos, then what the AI read,
    then the verdict heading. It makes the split visible: the AI only transcribes; the rules below do the judging."""
    unit = "ml" if label.get("is_liquid") else "g"
    pics = "".join(f'<figure><img src="{p}" alt=""><figcaption>{k}</figcaption></figure>'
                   for p, k in zip(photos, ("front", "ingredients", "nutrition", "more")))
    per100 = label.get("per_100") or {}
    rows = "".join(f'<tr><td>{name}</td><td class="ai">{fmt(float(per100[k]))} {u}</td></tr>'
                   for k, name, u in READ_FIELDS if per100.get(k) is not None)
    table = (f'<table class="ld-read"><tr><th>Per 100 {unit}</th><th>AI read</th></tr>{rows}</table>' if rows
             else '<div class="ld-callout">No nutrition numbers were read. The verdict below can only use the ingredient list.</div>')
    serve = f"{label['serving_size_g']:g} {unit}" if label.get("serving_size_g") else "None printed"
    facts = [("Pack", f"{label.get('brand') or ''} {label.get('product_name') or ''}".strip() or "Name not read", ""),
             ("Serve size printed", serve, ""),
             ("Claims on the front", ", ".join(label.get("front_of_pack_claims") or []) or "None read", "")]
    chips, n_items = ui._ing_chips(label, set(), flag=False, limit=40)      # plain chips: reading is not judging
    ing = (f'<div class="ld-order">{chips}</div>' if n_items else esc(label.get("ingredients_text") or "None read"))
    facts_html = ('<div class="ld-facts">' + "".join(f'<div{cls}><b>{esc(k)}</b>{esc(v)}</div>' for k, v, cls in facts)
                  + f'<div class=wide><b>Ingredients, in pack order (biggest first)</b>{ing}</div></div>')
    leg = {"good": "clean photos", "partial": "some glare or blur", "poor": "hard to read"}.get(label.get("legibility"), "")
    who = f" by {esc(label['read_by'])}" if label.get("read_by") else ""
    took = f"Read live in <b>{secs:.0f} seconds</b>{who}." if secs is not None else f"Read live{who}."
    warn = (f'<div class="ld-callout"><b>Hard to read.</b> Some numbers may be off: {esc(label.get("notes") or "")}</div>'
            if label.get("legibility") == "poor" else "")
    step = 1
    out = '<div class="ld-card">'
    if pics:
        out += (f'<div class="ld-flow"><span>{step}</span>The photos it was given</div>'
                f'<div class="ld-h2-sub">{esc(leg)}</div><div class="ld-photos">{pics}</div>')
        step += 1
    out += (f'<div class="ld-flow"><span>{step}</span>What the AI read. Nothing more: it only copies the pack</div>{table}{facts_html}'
            f'<div class="ld-mean">{took} The AI did not judge anything. Every verdict below comes from the written rules.</div>{warn}'
            f'<div class="ld-flow"><span>{step + 1}</span>The verdict, worked out from what the AI read</div></div>')
    return out
