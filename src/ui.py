"""
Presentation layer for the Streamlit app: CSS and HTML builders.

Nothing here judges a label. Every number comes from decode_label(); this module only decides
how to show it. The one piece of logic is the traffic light, which uses the UK FSA
front-of-pack thresholds (India has no final FOP standard yet) and is labelled as such.
"""

from __future__ import annotations

import html
import re

from src.rules.health import ingredient_flag
from src.rules.serving import TEASPOON_G, WHO_FREE_SUGAR_5PCT_G

# UK FSA front-of-pack thresholds per 100 g (food) / per 100 ml (drinks): (low <=, high >)
FSA_FOOD = {"sugar": (5.0, 22.5), "fat": (3.0, 17.5), "satfat": (1.5, 5.0), "salt": (0.3, 1.5)}
FSA_DRINK = {"sugar": (2.5, 11.25), "fat": (1.5, 8.75), "satfat": (0.75, 2.5), "salt": (0.3, 0.75)}

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Outfit:wght@600;700;800;900&family=Caveat:wght@600;700&display=swap');
:root{
  --ink:#1c1917; --muted:#57534e; --faint:#a8a29e; --line:#e7e5e4; --card:#ffffff; --bg:#f4f6f9;
  --red:#dc2626; --red-bg:#fef2f2; --amber:#d97706; --amber-bg:#fffbeb; --green:#16a34a; --green-bg:#f0fdf4;
  --brand:#4338ca; --brand-bg:#eef2ff; --sugar:#fde68a;
}
html, body, .stApp, .stApp p, .stApp label, .stApp summary, button, input, textarea { font-family:'Inter',system-ui,sans-serif !important; }
[data-testid="stIconMaterial"] { font-family:'Material Symbols Rounded' !important; }
.stApp { background-color:var(--bg); }
.block-container { max-width:1080px; padding-top:0.6rem; padding-bottom:3rem; }
#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"] { display:none !important; }
header[data-testid="stHeader"] { background:transparent; height:0; }
.ld-h2, .ld-name, .ld-hero h1, .ld-big, .ld-cmp .nm, .ld-cmp .big, .ld-stat b { font-family:'Outfit','Inter',sans-serif !important; }

/* top bar */
.ld-nav { position:sticky; top:0; z-index:50; display:flex; align-items:center; justify-content:space-between; gap:12px;
  background:#ffffff; border:1px solid var(--line); border-radius:14px;
  padding:10px 16px; margin:4px 0 16px; box-shadow:0 6px 20px rgba(28,25,23,.05); }
.ld-nav .logo { display:flex; align-items:center; gap:10px; font-family:'Outfit',sans-serif; font-weight:800; font-size:18px; color:var(--ink); }
.ld-nav .logo i { font-style:normal; display:grid; place-items:center; width:34px; height:34px; border-radius:10px; background:linear-gradient(135deg,#334155,#0f172a); color:#fff; font-size:18px; box-shadow:0 4px 10px rgba(67,56,202,.35); }
.ld-nav .links { display:flex; gap:8px; align-items:center; }
.ld-nav a { text-decoration:none; font-weight:600; font-size:13.5px; color:var(--muted); padding:7px 12px; border-radius:999px; border:1px solid transparent; }
.ld-nav a:hover { background:#fff; border-color:var(--line); color:var(--ink); }
.ld-nav a.cta { background:var(--ink); color:#fff; }
.ld-nav a.cta:hover { background:#292524; border-color:transparent; color:#fff; }

/* tabs -> pill segmented control */
.stTabs [data-baseweb="tab-list"] { gap:6px; border-bottom:none; flex-wrap:wrap; background:#fff; border:1px solid var(--line); border-radius:999px; padding:5px; width:fit-content; max-width:100%; }
.stTabs [data-baseweb="tab"] { padding:8px 16px; border-radius:999px; font-weight:600; color:var(--muted); transition:all .15s; }
.stTabs [data-baseweb="tab"]:hover { background:#fafaf9; color:var(--ink); }
.stTabs [aria-selected="true"] { color:#fff !important; background:linear-gradient(135deg,#334155,#0f172a); box-shadow:0 4px 12px rgba(15,23,42,.3); }
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] { display:none; }
.stTabs [data-baseweb="tab-panel"] { padding-top:18px; }

/* streamlit widgets */
.stButton button, .stDownloadButton button { border-radius:999px; font-weight:700; border:1px solid var(--line); transition:all .15s; }
.stButton button:hover, .stDownloadButton button:hover { transform:translateY(-1px); border-color:#a5b4fc; color:var(--brand); }
.stButton button[kind="primary"], .stDownloadButton button[kind="primary"] { background:linear-gradient(135deg,#334155,#0f172a); border:none; color:#fff; box-shadow:0 6px 16px rgba(15,23,42,.3); }
.stButton button[kind="primary"]:hover { color:#fff; box-shadow:0 8px 20px rgba(15,23,42,.4); }
.stTextInput input, .stTextArea textarea { border-radius:14px !important; border:1.5px solid var(--line) !important; background:#fff !important; font-size:15px; padding:12px 14px; }
.stTextInput input:focus, .stTextArea textarea:focus { border-color:var(--brand) !important; box-shadow:0 0 0 4px rgba(67,56,202,.15) !important; }
[data-baseweb="select"] > div { border-radius:14px !important; border:1.5px solid var(--line) !important; background:#fff !important; }
[data-testid="stFileUploader"] section { border:2px dashed #a5b4fc; border-radius:18px; background:#fff; }
[data-testid="stExpander"] { border:1px solid var(--line); border-radius:14px; background:#fff; }
/* product picker: a bordered st.container holding a .ld-pcard is drawn as the site's .ld-pc card (Streamlit 1.61 markup) */
[data-testid="stVerticalBlock"]:has(> .stElementContainer > .stHtml > .ld-pcard) {
  background:var(--card); border-radius:18px !important; border:1px solid var(--line) !important; padding:12px !important; gap:10px; }
[data-testid="stVerticalBlock"]:has(> .stElementContainer > .stHtml > .ld-pcard.on) { border-color:#818cf8 !important; box-shadow:0 0 0 4px rgba(67,56,202,.15), 0 12px 28px rgba(15,23,42,.12) !important; }
.ld-ribbon { position:absolute; top:10px; left:-6px; background:linear-gradient(135deg,#dc2626,#ef4444); color:#fff; font-size:11px; font-weight:800; letter-spacing:.04em; padding:4px 10px; border-radius:0 999px 999px 0; box-shadow:0 3px 8px rgba(220,38,38,.3); }
.ld-ribbon.gold { background:linear-gradient(135deg,#d97706,#f59e0b); box-shadow:0 3px 8px rgba(217,119,6,.3); }
.ld-ribbon.green { background:linear-gradient(135deg,#15803d,#22c55e); box-shadow:0 3px 8px rgba(21,128,61,.3); }

/* hero */
.ld-hero { position:relative; overflow:hidden; background:#ffffff; border:1px solid var(--line);
  border-radius:24px; padding:34px 34px 28px; margin-bottom:18px; box-shadow:0 1px 0 rgba(28,25,23,.04), 0 14px 34px rgba(28,25,23,.06); }
.ld-hero > * { position:relative; z-index:1; }
.ld-hero h1 em { color:var(--red); }
.ld-badge { display:inline-block; font-size:12px; font-weight:700; letter-spacing:.04em; text-transform:uppercase;
  color:var(--brand); background:#fff; border:1px solid #c7d2fe; border-radius:999px; padding:4px 12px; }
.ld-hero h1 { font-size:44px; line-height:1.08; font-weight:800; color:var(--ink); margin:14px 0 10px; letter-spacing:-.02em; padding:0; }
.ld-hero h1 em { font-style:normal; color:var(--red); }
.ld-hero p.sub { font-size:17px; color:var(--muted); max-width:680px; margin:0 0 14px; }
.ld-steps { display:flex; align-items:stretch; gap:10px; margin:0 0 20px; }
.ld-step { flex:1; background:#fff; border:1px solid var(--line); border-radius:16px; padding:14px 16px; }
.ld-step .ic { font-size:30px; line-height:1; margin-bottom:8px; }
.ld-step b { display:block; font-size:15px; color:var(--ink); }
.ld-step span { font-size:13px; color:var(--muted); }
.ld-arrow { align-self:center; font-size:26px; color:var(--brand); font-weight:800; }
.ld-stats { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; }
.ld-about { margin-top:0; }
.ld-ab-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin-top:4px; }
.ld-ab { background:#fafaf9; border:1px solid var(--line); border-radius:14px; padding:14px 16px; }
.ld-ab .ic { font-size:26px; line-height:1; margin-bottom:8px; }
.ld-ab b { display:block; font-size:15px; color:var(--ink); margin-bottom:4px; font-family:'Outfit',sans-serif; }
.ld-ab ul { margin:0; padding-left:18px; }
.ld-ab li { font-size:13.5px; line-height:1.5; color:var(--muted); margin:3px 0; }
.ld-ab li b { display:inline; font-family:inherit; font-size:inherit; color:var(--ink); }
.ld-pts { list-style:none; margin:0 0 22px; padding:0; display:grid; grid-template-columns:1fr 1fr; gap:8px 18px; }
.ld-pts li { display:flex; align-items:center; gap:10px; font-size:16px; color:var(--muted); background:#fff; border:1px solid var(--line); border-radius:12px; padding:9px 12px; }
.ld-pts li i { font-style:normal; font-size:22px; }
.ld-pts li b { color:var(--ink); }
.ld-mean { margin-top:14px; padding:10px 14px; border-radius:12px; background:#fafaf9; border-left:4px solid var(--brand); font-size:14.5px; color:var(--ink); }
.ld-mean b { color:var(--brand); }
.ld-budget { display:flex; flex-wrap:wrap; gap:8px; margin:10px 0 6px; }
.ld-cube.empty { background:#fff; border-style:dashed; border-color:#d6d3d1; box-shadow:none; }
.ld-cube.over { background:#fecaca; border-color:var(--red); box-shadow:inset -5px -5px 0 #fca5a5, 0 2px 0 #fca5a5; }
.ld-vs { display:grid; grid-template-columns:1fr auto 1fr; gap:12px; align-items:center; margin:14px 0 4px; }
.ld-vs .box { border-radius:14px; padding:14px; text-align:center; }
.ld-vs .box.a { background:#f5f5f4; } .ld-vs .box.b { background:var(--brand-bg); border:1px solid #c7d2fe; }
.ld-vs .box small { display:block; font-size:12px; font-weight:700; letter-spacing:.05em; text-transform:uppercase; color:var(--faint); }
.ld-vs .box b { display:block; font-size:26px; color:var(--ink); margin:4px 0; }
.ld-vs .box span { font-size:13px; color:var(--muted); }
.ld-vs .mid { font-size:22px; font-weight:800; color:var(--faint); }
.ld-stat { background:#fff; border:1px solid var(--line); border-radius:14px; padding:12px 14px; }
.ld-stat b { display:block; font-size:24px; font-weight:800; color:var(--ink); }
.ld-stat span { font-size:13px; color:var(--muted); }

/* marquee of findings under the hero */
.ld-marq { overflow:hidden; white-space:nowrap; border-top:1px solid #c7d2fe; border-bottom:1px solid #c7d2fe; background:#fff; margin:-6px 0 18px; border-radius:12px; }
.ld-marq div { display:inline-block; padding:10px 0; animation:ld-scroll 45s linear infinite; }
.ld-marq span { display:inline-block; margin:0 22px; font-size:14px; font-weight:600; color:var(--muted); }
.ld-marq span b { color:var(--ink); } .ld-marq span i { font-style:normal; color:var(--brand); margin-right:6px; }
@keyframes ld-scroll { from { transform:translateX(0); } to { transform:translateX(-50%); } }

.ld-ab-grid.two { grid-template-columns:repeat(2,1fr); }
/* language toggle: English by default, Hindi when <body class="lang-hi"> (never "hi": that would hide the body itself) */
.hi { display:none; } body.lang-hi .hi { display:inline; } body.lang-hi .en { display:none; }
.ld-lang { font:700 13px 'Inter',sans-serif; color:var(--ink); background:#fff; border:1.5px solid var(--line); border-radius:999px; padding:6px 12px; cursor:pointer; }
.ld-lang:hover { border-color:var(--brand); color:var(--brand); }
/* short hero */
.ld-ctas { display:flex; flex-wrap:wrap; gap:10px; margin:4px 0 16px; }
.ld-cta { display:inline-block; text-decoration:none; font:800 16px 'Inter',sans-serif; color:#fff; background:linear-gradient(135deg,#334155,#0f172a);
  border-radius:999px; padding:13px 26px; box-shadow:0 8px 20px rgba(15,23,42,.32); transition:transform .15s; }
.ld-cta:hover { transform:translateY(-2px); }
.ld-cta.ghost { background:#fff; color:var(--ink); border:1.5px solid var(--line); box-shadow:none; }
.ld-proof { font-size:14px; color:var(--muted); }
.ld-proof b { color:var(--ink); }
/* 3 things to know */
.ld-3 { display:grid; gap:10px; margin-top:6px; }
.ld-3 > div { display:grid; grid-template-columns:34px 1fr; gap:12px; align-items:center; background:#fafaf9; border:1px solid var(--line); border-radius:14px; padding:12px 14px; font-size:16px; color:var(--muted); }
.ld-3 > div > i { font-style:normal; display:grid; place-items:center; width:34px; height:34px; border-radius:50%; background:linear-gradient(135deg,#334155,#0f172a); color:#fff; font:800 16px 'Outfit',sans-serif; }
.ld-3 b { color:var(--ink); }
.ld-hc-grid { display:grid; grid-template-columns:repeat(4, 1fr); gap:10px; margin-top:6px; }
.ld-hc-t { border:1px solid var(--line); border-top-width:5px; border-radius:14px; padding:13px 14px 14px; background:#fafaf9; }
.ld-hc-t .top { display:flex; align-items:center; justify-content:space-between; gap:8px; font-size:12.5px; font-weight:800; letter-spacing:.05em; text-transform:uppercase; color:var(--muted); }
.ld-hc-t .top em { font-style:normal; font-size:11px; padding:3px 9px; border-radius:999px; background:#e7e5e4; color:var(--muted); white-space:nowrap; letter-spacing:.06em; }
.ld-hc-t .hd { font:800 17px/1.25 'Outfit','Inter',sans-serif; color:var(--ink); margin:9px 0 7px; }
.ld-hc-t ul { list-style:none; margin:0; padding:0; display:grid; gap:5px; font-size:13.5px; line-height:1.4; color:#44403c; }
.ld-hc-t li { position:relative; padding-left:14px; margin:0; }
.ld-hc-t li::before { content:""; position:absolute; left:0; top:.52em; width:6px; height:6px; border-radius:50%; background:#a8a29e; }
.ld-hc-t.red { background:var(--red-bg); border-color:#fecaca; border-top-color:var(--red); } .ld-hc-t.red .top em { background:var(--red); color:#fff; } .ld-hc-t.red li::before { background:var(--red); }
.ld-hc-t.amber { background:#fefce8; border-color:#fde047; border-top-color:#eab308; } .ld-hc-t.amber .top em { background:#facc15; color:#422006; } .ld-hc-t.amber li::before { background:#ca8a04; }
.ld-hc-t.green { background:var(--green-bg); border-color:#bbf7d0; border-top-color:var(--green); } .ld-hc-t.green .top em { background:var(--green); color:#fff; } .ld-hc-t.green li::before { background:var(--green); }
.ld-hc-rule { margin-top:12px; font-size:14px; color:var(--muted); }
.ld-hc-rule b { color:var(--ink); }
.ld-vban .vt { font-size:13px; font-weight:600; opacity:.92; margin-top:7px; }
.ld-order span.bad { background:var(--red-bg); border-color:#fecaca; color:#7f1d1d; font-weight:600; }
.ld-order span.bad b { background:var(--red); color:#fff; }
@media (max-width: 900px) { .ld-hc-grid { grid-template-columns:repeat(2, 1fr); } }
@media (max-width: 520px) { .ld-hc-grid { grid-template-columns:1fr; } }
/* icons: one stroke set, drawn as CSS masks so they take the text colour (see ICONS) */
.ld-ic { display:inline-block; width:1.15em; height:1.15em; vertical-align:-.2em; font-style:normal; background:currentColor;
  -webkit-mask:var(--m) center / contain no-repeat; mask:var(--m) center / contain no-repeat; }
.ld-h2 .ld-ic { color:var(--brand); margin-right:4px; }
.ld-ab .ic .ld-ic { color:var(--brand); }
.ld-bigic { font-size:44px; line-height:1; color:var(--brand); }
/* hero: the same pack, front and back */
.ld-hero-grid { display:grid; grid-template-columns:1.2fr .8fr; gap:26px; align-items:center; }
.ld-hero-grid h1 { font-size:38px; }
.ld-pack { position:relative; height:286px; }
.ld-face { position:absolute; width:186px; height:236px; border-radius:18px; padding:16px 14px; box-sizing:border-box; box-shadow:0 18px 40px rgba(15,23,42,.2); }
.ld-face .tag { position:absolute; top:-11px; left:14px; font:800 10px 'Inter',sans-serif; letter-spacing:.09em; background:var(--ink); color:#fff; border-radius:999px; padding:3px 10px; }
.ld-face.front { left:0; top:18px; transform:rotate(-6deg); background:linear-gradient(160deg,#22c55e,#15803d); color:#fff; }
.ld-face.front .br { font:800 10px 'Inter',sans-serif; letter-spacing:.14em; opacity:.85; }
.ld-face.front .hl { font:900 30px 'Outfit',sans-serif; line-height:1; margin:10px 0 12px; }
.ld-face.front .ck { display:block; font:700 12px 'Inter',sans-serif; background:rgba(255,255,255,.2); border-radius:999px; padding:5px 10px; margin:6px 0; width:fit-content; }
.ld-face.front .sun { position:absolute; right:-18px; bottom:-18px; width:86px; height:86px; border-radius:50%; background:rgba(255,255,255,.16); }
.ld-face.back { right:0; top:30px; transform:rotate(5deg); background:#fff; border:1px solid var(--line); color:var(--muted); }
.ld-face.back .h { font:800 10px 'Inter',sans-serif; letter-spacing:.12em; color:var(--faint); margin-bottom:6px; }
.ld-face.back .t { font-size:12px; line-height:1.75; }
.ld-face.back mark { background:var(--sugar); color:#78350f; font-weight:700; border-radius:4px; padding:0 3px; animation:ld-glow 3.6s ease-in-out infinite; }
.ld-face.back mark:nth-of-type(2){animation-delay:.3s} .ld-face.back mark:nth-of-type(3){animation-delay:.6s} .ld-face.back mark:nth-of-type(4){animation-delay:.9s}
@keyframes ld-glow { 0%,70%,100% { box-shadow:none; } 35% { box-shadow:0 0 0 3px rgba(245,158,11,.35); } }
.ld-face.back .cb { display:flex; gap:5px; margin:12px 0 6px; }
.ld-face.back .cb i { width:20px; height:20px; border-radius:5px; background:#f1f5f9; border:2px solid #94a3b8; box-shadow:inset -3px -3px 0 #cbd5e1; animation:ld-drop 3.6s ease-in-out infinite; }
.ld-face.back .cb i:nth-child(2){animation-delay:.12s} .ld-face.back .cb i:nth-child(3){animation-delay:.24s} .ld-face.back .cb i:nth-child(4){animation-delay:.36s} .ld-face.back .cb i:nth-child(5){animation-delay:.48s}
@keyframes ld-drop { 0%,8% { transform:translateY(-14px) scale(.4); opacity:0; } 22%,100% { transform:none; opacity:1; } }
.ld-face.back .eq { font:800 14px 'Outfit',sans-serif; color:var(--red); }
.ld-pack-cap { position:absolute; left:0; right:0; bottom:0; text-align:center; font:700 13px 'Inter',sans-serif; color:var(--muted); }
/* result: full-width verdict banner */
.ld-card.ld-vcard { padding:0; overflow:hidden; }
.ld-vcard .ld-top { padding:20px 24px 22px; }
.ld-vban { display:flex; align-items:center; justify-content:space-between; gap:16px; flex-wrap:wrap; padding:16px 24px; color:#fff; }
.ld-vban.red { background:linear-gradient(135deg,#dc2626,#b91c1c); } .ld-vban.amber { background:linear-gradient(135deg,#facc15,#eab308); color:#422006; }
.ld-vban.green { background:linear-gradient(135deg,#16a34a,#15803d); }
.ld-vban .v { display:flex; align-items:center; gap:10px; font:900 30px 'Outfit',sans-serif; line-height:1; }
.ld-vban .s { font-size:14.5px; font-weight:600; opacity:.95; text-align:right; }
.ld-vban .s b { font:900 34px 'Outfit',sans-serif; line-height:1; margin-right:6px; vertical-align:-3px; }
@media (prefers-reduced-motion: reduce) { .ld-face.back mark, .ld-face.back .cb i { animation:none; } }

/* dashboard lead */
.ld-lead { background:linear-gradient(135deg,#fef2f2,#ffffff); border:1px solid #fecaca; border-radius:18px; padding:20px 24px; margin:0 0 14px; }
.ld-lead .big { font:800 30px 'Outfit',sans-serif; color:var(--ink); line-height:1.2; }
.ld-lead .big em { font-style:normal; color:var(--red); }
.ld-lead .sm { font-size:15.5px; color:var(--muted); margin-top:6px; }

/* dashboard */
.ld-kpis { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin:6px 0 14px; }
.ld-kpi { background:var(--card); border:1px solid var(--line); border-radius:16px; padding:16px 18px; animation:ld-in .4s ease both; }
.ld-kpi b { display:block; font-family:'Outfit',sans-serif; font-size:38px; line-height:1; color:var(--ink); }
.ld-kpi b small { font-size:17px; color:var(--faint); font-weight:700; }
.ld-kpi span { display:block; font-size:13.5px; color:var(--muted); margin-top:6px; line-height:1.35; }
.ld-kpi.red b { color:var(--red); } .ld-kpi.amber b { color:var(--amber); }
.ld-donut-wrap { display:flex; align-items:center; gap:22px; }
.ld-donut { width:150px; height:150px; flex:none; border-radius:50%; display:grid; place-items:center; }
.ld-donut::before { content:attr(data-v); width:98px; height:98px; border-radius:50%; background:var(--card); display:grid; place-items:center;
  font-family:'Outfit',sans-serif; font-size:30px; font-weight:800; color:var(--ink); }
.ld-legend div { font-size:14.5px; color:var(--muted); margin:7px 0; }
.ld-legend i { display:inline-block; width:12px; height:12px; border-radius:3px; margin-right:8px; vertical-align:-1px; }
.ld-legend b { color:var(--ink); }
.ld-stackrow { display:grid; grid-template-columns:104px 1fr; gap:10px; align-items:center; margin:11px 0; font-size:14px; color:var(--muted); }
.ld-stack { display:flex; height:22px; border-radius:999px; overflow:hidden; background:#f5f5f4; }
.ld-stack i { display:block; height:100%; font-style:normal; font-size:11px; font-weight:800; color:#fff; text-align:center; line-height:22px; }
.ld-hrow { display:grid; grid-template-columns:minmax(120px,38%) 1fr 54px; gap:10px; align-items:center; margin:8px 0; font-size:13.5px; color:var(--muted); }
.ld-hrow .n { white-space:nowrap; overflow:hidden; text-overflow:ellipsis; color:var(--ink); font-weight:600; }
.ld-hrow .t { height:14px; background:#f5f5f4; border-radius:999px; overflow:hidden; }
.ld-hrow .t i { display:block; height:100%; border-radius:999px; animation:ld-grow .7s ease-out both; transform-origin:left; }
.ld-hrow .v { text-align:right; font-weight:800; color:var(--ink); }
/* AI replay */
.ld-photos { display:grid; grid-template-columns:repeat(3,1fr); gap:10px; margin:8px 0 4px; }
.ld-photos figure { margin:0; background:#fafaf9; border:1px solid var(--line); border-radius:12px; padding:8px; text-align:center; }
.ld-photos img { width:100%; height:150px; object-fit:contain; border-radius:8px; background:#fff; }
.ld-photos figcaption { font-size:12px; font-weight:700; color:var(--faint); margin-top:6px; text-transform:uppercase; letter-spacing:.05em; }
.ld-read { width:100%; border-collapse:collapse; font-size:14.5px; margin-top:6px; }
.ld-read th { text-align:left; font-size:11px; letter-spacing:.06em; text-transform:uppercase; color:var(--faint); padding:6px 10px; border-bottom:1px solid var(--line); }
.ld-read td { padding:8px 10px; border-bottom:1px solid #f5f5f4; color:var(--muted); }
.ld-read td:first-child { color:var(--ink); font-weight:600; }
.ld-read td.ai { font-weight:800; color:var(--ink); }
.ld-read tr.bad td { background:var(--red-bg); } .ld-read .ok { color:var(--green); font-weight:800; } .ld-read .no { color:var(--red); font-weight:800; }
.ld-flow { display:flex; align-items:center; gap:10px; margin:18px 0 10px; font-family:'Outfit',sans-serif; font-weight:800; font-size:17px; color:var(--ink); }
.ld-flow:first-child { margin-top:0; }
.ld-flow span { display:grid; place-items:center; width:30px; height:30px; border-radius:50%; background:linear-gradient(135deg,#334155,#0f172a); color:#fff; font-size:15px; }
.ld-chips { display:flex; flex-wrap:wrap; gap:8px; margin:4px 0 14px; }
.ld-chips button { font:600 14px 'Inter',sans-serif; color:var(--ink); background:#fff; border:1.5px solid var(--line); border-radius:999px; padding:8px 14px; cursor:pointer; }
.ld-chips button.on { border-color:var(--brand); background:var(--brand-bg); color:var(--brand); }
.ld-chips button i { font-style:normal; font-size:12px; font-weight:800; margin-left:6px; padding:1px 7px; border-radius:999px; background:var(--green-bg); color:var(--green); }
.ld-chips button i.miss { background:var(--red-bg); color:var(--red); }

/* per-tab intro strip */
.ld-intro { display:grid; grid-template-columns:150px 1fr; gap:18px; align-items:center; background:#fff; border:1px solid var(--line);
  border-radius:18px; padding:16px 20px; margin:0 0 16px; animation:ld-in .35s ease both; }
.ld-intro .art { display:flex; align-items:center; justify-content:center; height:96px; background:#eef1f5; border-radius:14px; }
.ld-intro .t { font-family:'Outfit',sans-serif; font-size:22px; font-weight:800; color:var(--ink); }
.ld-intro .l { font-size:15.5px; color:var(--muted); margin:3px 0 8px; }
.ld-intro .tip { font-size:13.5px; color:var(--muted); background:#fafaf9; border-radius:10px; padding:7px 10px; display:inline-block; }
.ld-intro .tip b { color:var(--brand); margin-right:6px; }
.ld-art span { font-size:34px; margin:0 3px; display:inline-block; animation:ld-bob 2.4s ease-in-out infinite; }
.ld-art span:nth-child(2){animation-delay:.3s} .ld-art span:nth-child(3){animation-delay:.6s} .ld-art span:nth-child(4){animation-delay:.9s}
@keyframes ld-bob { 0%,100% { transform:translateY(0); } 50% { transform:translateY(-6px); } }
.ld-barcode { text-align:center; }
.ld-barcode .bars { width:110px; height:46px; margin:0 auto; background:repeating-linear-gradient(90deg,#1c1917 0 2px,transparent 2px 4px,#1c1917 4px 7px,transparent 7px 9px,#1c1917 9px 10px,transparent 10px 13px); }
.ld-barcode .num { font-family:monospace; font-size:12px; letter-spacing:2px; color:var(--ink); margin-top:4px; }
.ld-frames { display:flex; gap:6px; }
.ld-frames div { width:38px; height:54px; border:2px dashed #818cf8; border-radius:6px; font-size:8px; font-weight:700; color:var(--brand); display:flex; align-items:flex-end; justify-content:center; padding-bottom:3px; background:#fff; }
.ld-typed { font-family:monospace; font-size:10.5px; line-height:1.5; color:var(--muted); background:#fff; border:1px solid var(--line); border-radius:8px; padding:8px 10px; text-align:left; }
.ld-vsbadge { display:flex; align-items:center; gap:8px; }
.ld-vsbadge span { width:38px; height:38px; border-radius:50%; background:#fff; border:2px solid var(--line); display:grid; place-items:center; font-weight:800; color:var(--ink); }
.ld-vsbadge b { font-family:'Outfit',sans-serif; font-size:22px; color:var(--brand); }

/* product picker cards */
[data-testid="stVerticalBlock"]:has(> .stElementContainer > .stHtml > .ld-pcard) { transition:transform .18s ease, box-shadow .18s ease; }
[data-testid="stVerticalBlock"]:has(> .stElementContainer > .stHtml > .ld-pcard):hover { transform:translateY(-3px); box-shadow:0 10px 24px rgba(28,25,23,.08); }
.ld-pcard { text-align:center; position:relative; }
.ld-pcard .img { height:128px; display:flex; align-items:center; justify-content:center; background:#f1f5f9; border-radius:14px; padding:10px; box-sizing:border-box; overflow:hidden; }
.ld-pcard img { transition:transform .25s ease; }
[data-testid="stVerticalBlock"]:has(> .stElementContainer > .stHtml > .ld-pcard):hover .ld-pcard img { transform:scale(1.07); }
.ld-pcard img { max-height:100%; max-width:100%; object-fit:contain; border-radius:8px; box-shadow:0 4px 10px rgba(15,23,42,.12); }
.ld-pcard .nm { font-weight:700; font-size:14px; color:var(--ink); margin-top:8px; line-height:1.25; min-height:36px; }
.ld-chip { display:inline-block; font-size:12px; font-weight:700; border-radius:999px; padding:2px 10px; margin-top:6px; }
.ld-chip.red { background:var(--red-bg); color:var(--red); } .ld-chip.amber { background:var(--amber-bg); color:var(--amber); }
.ld-chip.green { background:var(--green-bg); color:var(--green); } .ld-chip.grey { background:#f5f5f4; color:var(--muted); }

/* result */
.ld-card { background:var(--card); border:1px solid var(--line); border-radius:18px; padding:22px 24px; margin:14px 0; animation:ld-in .35s ease both; }
@keyframes ld-in { from { opacity:0; transform:translateY(8px); } to { opacity:1; transform:none; } }
.ld-ring { display:flex; align-items:center; gap:18px; margin-top:4px; }
.ld-ring .r { width:112px; height:112px; flex:none; border-radius:50%; display:grid; place-items:center;
  background:conic-gradient(var(--c) calc(var(--p) * 1%), #f5f5f4 0); }
.ld-ring .r::before { content:attr(data-v); width:84px; height:84px; border-radius:50%; background:var(--card);
  display:grid; place-items:center; font-size:23px; font-weight:800; color:var(--ink); }

/* distribution strip */
.ld-dist { display:flex; align-items:flex-end; gap:2px; height:70px; margin:14px 0 6px; }
.ld-dist i { flex:1; display:block; background:#d6d3d1; border-radius:2px 2px 0 0; min-height:3px; }
.ld-dist i.me { background:var(--brand); flex:2.5; border-radius:3px; box-shadow:0 0 0 3px #fff, 0 0 0 5px var(--brand); position:relative; z-index:1; }
.ld-dist-axis { display:flex; justify-content:space-between; font-size:12px; color:var(--faint); }

/* ingredient order */
.ld-order { display:flex; flex-wrap:wrap; gap:8px; margin-top:8px; }
.ld-order span { display:inline-flex; align-items:center; gap:7px; background:#fafaf9; border:1px solid var(--line); border-radius:999px; padding:5px 12px 5px 6px; font-size:13.5px; color:var(--muted); }
.ld-order span b { display:inline-flex; width:22px; height:22px; border-radius:50%; background:#e7e5e4; color:var(--ink); font-size:12px; align-items:center; justify-content:center; }
.ld-order span.sug { background:var(--sugar); border-color:#fcd34d; color:#78350f; font-weight:700; }
.ld-order span.sug b { background:#f59e0b; color:#fff; }
.ld-callout { margin-top:14px; padding:12px 14px; border-radius:12px; background:var(--red-bg); border:1px solid #fecaca; color:#7f1d1d; font-size:14.5px; }
.ld-callout b { font-size:16px; }

/* compare */
.ld-cmp { background:var(--card); border:1px solid var(--line); border-radius:18px; padding:18px; text-align:center; height:100%; }
.ld-cmp .img { height:140px; display:flex; align-items:center; justify-content:center; background:#f1f5f9; border-radius:14px; padding:10px; box-sizing:border-box; }
.ld-cmp .img img { max-height:100%; max-width:100%; object-fit:contain; border-radius:8px; box-shadow:0 4px 10px rgba(15,23,42,.12); }
.ld-cmp .nm { font-size:20px; font-weight:800; color:var(--ink); margin:8px 0 6px; }
.ld-cmp .big { font-size:34px; font-weight:800; color:var(--ink); margin-top:10px; line-height:1; }
.ld-cmp .big small { font-size:14px; color:var(--muted); font-weight:600; }
.ld-cmp .mini { display:grid; grid-template-columns:repeat(4,1fr); gap:6px; margin-top:14px; }
.ld-cmp .mini div { border-radius:10px; padding:8px 4px; font-size:11px; font-weight:700; }
.ld-cmp .mini div b { display:block; font-size:14px; color:var(--ink); }
.ld-cmp .mini .red { background:var(--red-bg); color:var(--red); } .ld-cmp .mini .amber { background:var(--amber-bg); color:var(--amber); }
.ld-cmp .mini .green { background:var(--green-bg); color:var(--green); } .ld-cmp .mini .grey { background:#f5f5f4; color:var(--faint); }
.ld-cmp .win { margin-top:12px; font-size:13px; font-weight:700; color:var(--green); }
.ld-h2 { font-size:20px; font-weight:800; color:var(--ink); margin:0 0 4px; }
.ld-h2-sub { font-size:14px; color:var(--muted); margin:0 0 16px; }
.ld-top { display:grid; grid-template-columns:180px 1fr; gap:24px; align-items:center; }
.ld-top .img { background:#f1f5f9; border-radius:16px; height:180px; display:flex; align-items:center; justify-content:center; padding:12px; box-sizing:border-box; }
.ld-top .img img { max-height:100%; max-width:100%; object-fit:contain; border-radius:10px; box-shadow:0 6px 14px rgba(15,23,42,.14); }
.ld-top .img .ph { font-size:56px; }
.ld-brand { font-size:13px; font-weight:700; letter-spacing:.05em; text-transform:uppercase; color:var(--faint); }
.ld-name { font-size:30px; font-weight:800; color:var(--ink); line-height:1.15; margin:2px 0 12px; letter-spacing:-.01em; }
.ld-verdict { display:inline-flex; align-items:center; gap:8px; font-weight:800; font-size:15px; border-radius:999px; padding:6px 14px; }
.ld-verdict.red { background:var(--red); color:#fff; } .ld-verdict.amber { background:var(--amber); color:#fff; }
.ld-verdict.green { background:var(--green); color:#fff; }
.ld-headline { font-size:19px; font-weight:600; color:var(--ink); margin:14px 0 8px; line-height:1.4; }
.ld-reasons { margin:0; padding-left:18px; color:var(--muted); font-size:15px; }
.ld-reasons li { margin:3px 0; }
.ld-meta { font-size:13px; color:var(--faint); margin-top:12px; }

.ld-grid2 { display:grid; grid-template-columns:1.15fr 1fr; gap:14px; }
.ld-grid2 > .ld-card { margin:0; }
.ld-cubes { display:flex; flex-wrap:wrap; gap:8px; margin:6px 0 12px; }
.ld-cube { width:34px; height:34px; border-radius:8px; background:#f1f5f9; border:2px solid #94a3b8;
  box-shadow:inset -5px -5px 0 #cbd5e1, 0 2px 0 #cbd5e1; position:relative; overflow:hidden; animation:ld-pop .4s cubic-bezier(.3,1.5,.6,1) both; }
.ld-cube:nth-child(2){animation-delay:.05s} .ld-cube:nth-child(3){animation-delay:.1s} .ld-cube:nth-child(4){animation-delay:.15s}
.ld-cube:nth-child(5){animation-delay:.2s} .ld-cube:nth-child(6){animation-delay:.25s} .ld-cube:nth-child(7){animation-delay:.3s}
.ld-cube:nth-child(8){animation-delay:.35s} .ld-cube:nth-child(9){animation-delay:.4s} .ld-cube:nth-child(n+10){animation-delay:.45s}
@keyframes ld-pop { from { transform:scale(0); opacity:0; } to { transform:scale(1); opacity:1; } }
.ld-bar > div, .ld-light, .ld-dist i { animation:ld-grow .7s ease-out both; transform-origin:left bottom; }
@keyframes ld-grow { from { transform:scaleX(0); } to { transform:scaleX(1); } }
.ld-light { animation:ld-in .4s ease both; }
.ld-dist i { animation:ld-rise .6s ease-out both; }
@keyframes ld-rise { from { transform:scaleY(0); } to { transform:scaleY(1); } }
@property --p { syntax:'<number>'; inherits:false; initial-value:0; }
.ld-ring .r { animation:ld-fill 1s ease-out both; }
@keyframes ld-fill { from { --p:0; } }
.ld-cube.part { border-style:dashed; }
.ld-cube.part::after { content:""; position:absolute; top:0; bottom:0; right:0; width:var(--empty); background:#fff; }
.ld-big { font-size:40px; font-weight:800; color:var(--ink); line-height:1; }
.ld-big small { font-size:17px; font-weight:600; color:var(--muted); }
.ld-note { font-size:13px; color:var(--faint); margin-top:6px; }
.ld-bar { height:14px; background:#f5f5f4; border-radius:999px; overflow:hidden; margin:12px 0 8px; }
.ld-bar > div { height:100%; border-radius:999px; }

.ld-lights { display:grid; grid-template-columns:repeat(4,1fr); gap:10px; }
.ld-light { border-radius:14px; padding:12px 14px; border:1px solid transparent; }
.ld-light .k { font-size:13px; font-weight:700; color:var(--muted); }
.ld-light .v { font-size:22px; font-weight:800; color:var(--ink); margin:2px 0; }
.ld-light .l { font-size:11px; font-weight:800; letter-spacing:.06em; }
.ld-light.red { background:var(--red-bg); border-color:#fecaca; } .ld-light.red .l { color:var(--red); }
.ld-light.amber { background:var(--amber-bg); border-color:#fde68a; } .ld-light.amber .l { color:var(--amber); }
.ld-light.green { background:var(--green-bg); border-color:#bbf7d0; } .ld-light.green .l { color:var(--green); }
.ld-light.grey { background:#fafaf9; border-color:var(--line); } .ld-light.grey .l { color:var(--faint); }

.ld-flag { border:1px solid var(--line); border-left:5px solid var(--faint); border-radius:12px; padding:14px 16px; margin:10px 0; background:#fff; }
.ld-flag.high { border-left-color:var(--red); } .ld-flag.medium { border-left-color:var(--amber); } .ld-flag.low { border-left-color:#eab308; }
.ld-flag .t { font-weight:700; color:var(--ink); font-size:16px; }
.ld-flag .d { color:var(--muted); font-size:14.5px; margin-top:4px; }
.ld-flag .r { color:var(--faint); font-size:12px; margin-top:8px; }
.ld-sev { font-size:11px; font-weight:800; letter-spacing:.06em; text-transform:uppercase; border-radius:6px; padding:2px 7px; margin-right:8px; vertical-align:2px; }
.ld-sev.high { background:var(--red-bg); color:var(--red); } .ld-sev.medium { background:var(--amber-bg); color:var(--amber); }
.ld-sev.low { background:#fefce8; color:#a16207; }

.ld-claim { display:grid; grid-template-columns:1fr 1.4fr; border:1px solid var(--line); border-radius:14px; overflow:hidden; margin:10px 0; }
.ld-claim > div { padding:14px 16px; }
.ld-claim .says { background:#fafaf9; border-right:1px solid var(--line); }
.ld-claim .lbl { font-size:11px; font-weight:800; letter-spacing:.06em; text-transform:uppercase; color:var(--faint); margin-bottom:4px; }
.ld-claim .q { font-size:18px; font-weight:700; color:var(--ink); }
.ld-claim .vd { font-weight:800; font-size:15px; }
.ld-claim .vd.red { color:var(--red); } .ld-claim .vd.amber { color:var(--amber); } .ld-claim .vd.green { color:var(--green); } .ld-claim .vd.grey { color:var(--muted); }
.ld-claim .ex { color:var(--muted); font-size:14px; margin-top:4px; }

.ld-names { display:flex; flex-wrap:wrap; gap:8px; margin:4px 0 14px; }
.ld-name-chip { background:var(--sugar); color:#78350f; font-weight:700; font-size:13.5px; border-radius:8px; padding:4px 10px; }
.ld-name-chip i { font-style:normal; font-weight:500; opacity:.75; }
.ld-ing { font-size:14.5px; line-height:1.85; color:var(--muted); background:#fafaf9; border-radius:12px; padding:14px 16px; }
.ld-ing mark { background:var(--sugar); color:#78350f; font-weight:700; border-radius:4px; padding:1px 4px; }

.ld-honest { font-size:15.5px; line-height:1.6; color:var(--ink); background:var(--brand-bg); border:1px dashed #a5b4fc; border-radius:14px; padding:16px 18px; }
.ld-footer { text-align:center; color:var(--faint); font-size:13.5px; margin-top:36px; padding-top:18px; border-top:1px solid var(--line); }
.ld-footer a { color:var(--brand); text-decoration:none; font-weight:600; }
.ld-empty { background:#fff; border:1px dashed var(--line); border-radius:16px; padding:22px; color:var(--muted); text-align:center; }

@media (max-width: 720px) {
  .ld-hero { padding:24px 18px 20px; } .ld-hero h1 { font-size:31px; }
  .ld-hero-grid h1 { font-size:31px; }
  .ld-hero-grid { grid-template-columns:1fr; gap:10px; } .ld-pack { height:262px; max-width:330px; margin:0 auto; width:100%; }
  .ld-face { width:164px; height:214px; } .ld-face.front .hl { font-size:26px; }
  .ld-vban { padding:14px 16px; } .ld-vban .v { font-size:24px; } .ld-vban .s { text-align:left; } .ld-vban .s b { font-size:28px; }
  .ld-vcard .ld-top { padding:16px; }
  .ld-steps { flex-direction:column; } .ld-arrow { transform:rotate(90deg); text-align:center; }
  .ld-ab-grid { grid-template-columns:1fr; } .ld-pts { grid-template-columns:1fr; }
  .ld-intro { grid-template-columns:1fr; } .ld-intro .art { height:80px; }
  .ld-lead .big { font-size:23px; } .ld-3 > div { font-size:15px; } .ld-ab-grid.two { grid-template-columns:1fr; }
  .ld-kpis { grid-template-columns:repeat(2,1fr); } .ld-donut-wrap { flex-direction:column; align-items:flex-start; }
  .ld-photos img { height:96px; } .ld-hrow { grid-template-columns:minmax(96px,40%) 1fr 46px; }
  .ld-vs { grid-template-columns:1fr; } .ld-vs .mid { text-align:center; }
  .ld-stats, .ld-lights { grid-template-columns:repeat(2,1fr); }
  .ld-top { grid-template-columns:1fr; } .ld-top .img { height:150px; }
  .ld-name { font-size:24px; } .ld-grid2 { grid-template-columns:1fr; }
  .ld-claim { grid-template-columns:1fr; } .ld-claim .says { border-right:none; border-bottom:1px solid var(--line); }
}
</style>
"""


# One icon set instead of emoji (which change shape on every phone). 24x24, stroke only.
# Drawn as CSS masks, not inline <svg>: Streamlit's st.html strips <svg>, and a mask takes the text colour.
ICONS = {
    "spoon": "<ellipse cx='12' cy='7.5' rx='4' ry='4.5'/><path d='M12 12v9'/>",
    "calendar": "<rect x='3' y='5' width='18' height='16' rx='2'/><path d='M3 10h18M8 3v4M16 3v4'/>",
    "bars": "<path d='M4 21h16M6 21V11M12 21V4M18 21v-7'/>",
    "lights": "<rect x='8' y='2' width='8' height='20' rx='3'/><circle cx='12' cy='7' r='1'/><circle cx='12' cy='12' r='1'/><circle cx='12' cy='17' r='1'/>",
    "chat": "<path d='M4 5h16v11H10l-6 4z'/>",
    "wand": "<path d='M4 20L15 9M18 3v4M16 5h4M20 12v2M19 13h2M9 3v2M8 4h2'/>",
    "list": "<path d='M9 6h11M9 12h11M9 18h11M4.5 6h.01M4.5 12h.01M4.5 18h.01'/>",
    "eye": "<path d='M2 12s4-7 10-7 10 7 10 7-4 7-10 7-10-7-10-7z'/><circle cx='12' cy='12' r='3'/>",
    "check": "<circle cx='12' cy='12' r='9'/><path d='M8 12l3 3 5-6'/>",
    "cross": "<circle cx='12' cy='12' r='9'/><path d='M9 9l6 6M15 9l-6 6'/>",
    "alert": "<path d='M12 3l10 18H2z'/><path d='M12 10v5M12 18h.01'/>",
    "question": "<circle cx='12' cy='12' r='9'/><path d='M9.5 9.5a2.5 2.5 0 115 0c0 2-2.5 2-2.5 4M12 17h.01'/>",
    "target": "<circle cx='12' cy='12' r='9'/><circle cx='12' cy='12' r='5'/><circle cx='12' cy='12' r='1'/>",
    "phone": "<rect x='7' y='2' width='10' height='20' rx='2'/><path d='M11 18h2'/>",
    "book": "<path d='M5 4h11a3 3 0 013 3v13H8a3 3 0 01-3-3z'/><path d='M5 17a3 3 0 013-3h11'/>",
    "gear": "<circle cx='12' cy='12' r='3'/><path d='M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1L7 17M17 7l2.1-2.1'/>",
    "user": "<circle cx='12' cy='8' r='4'/><path d='M4 21c0-4 4-6 8-6s8 2 8 6'/>",
    "search": "<circle cx='11' cy='11' r='7'/><path d='M21 21l-4.5-4.5'/>",
    "download": "<path d='M12 3v12M7 11l5 5 5-5M4 21h16'/>",
    "medal": "<circle cx='12' cy='9' r='6'/><path d='M9 14l-2 7 5-3 5 3-2-7'/>",
    "package": "<path d='M3 8l9-5 9 5v8l-9 5-9-5z'/><path d='M3 8l9 5 9-5M12 13v8'/>",
}


def _icon_css() -> str:
    rules = []
    for name, body in ICONS.items():
        svg = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' "
               f"stroke-linecap='round' stroke-linejoin='round'>{body}</svg>")
        rules.append(f'.ld-ic-{name} {{ --m:url("data:image/svg+xml,{svg.replace("<", "%3C").replace(">", "%3E")}"); }}')
    return "\n".join(rules)


CSS = CSS.replace("</style>", _icon_css() + "\n</style>")

# The page background is drawn, not generated. Three quiet layers:
#   paper   - a warm off-white with a little grain and a very light dot grid (a designer's notebook, not a tech grid)
#   sketches - pen doodles of the things this project is about (barcode, spoon, sugar cube, pack, magnifier, per cent),
#              placed as a column in each page margin. They never sit behind content and never get cut by a card,
#              which is what made the earlier all-over pattern read as wallpaper.
# All of it is CSS, so it costs no requests.
_DOODLES = """
<g transform='translate(42 40) rotate(-8)'><path d='M0 0v46M7 1v44M12 0v46M21 2v43M26 0v46M30 1v45M39 0v46M46 2v43M51 0v46M60 1v44'/><path d='M-4 54c20 3 46-2 68 1'/></g>
<g transform='translate(78 250) rotate(22)'><path d='M0 0c-10 2-15 14-12 26c3 11 13 15 21 11c9-5 12-18 7-28c-3-6-9-10-16-9z'/><path d='M4 38c1 22-1 46 2 70'/></g>
<g transform='translate(46 520) rotate(-6)'><path d='M0 14l26-13l27 12l-1 30l-27 14l-26-13z'/><path d='M0 14l26 13l27-14M26 27l-1 30'/></g>
<g transform='translate(44 770) rotate(6)'><path d='M2 10c18-3 38-2 56 0l2 78c-20 3-40 3-60 0z'/><path d='M2 10l6-8l7 8l7-8l7 8l7-8l7 8l7-8l8 8'/><path d='M14 38h34M14 50h26M14 62h30'/></g>
<g transform='translate(40 1030) rotate(-12)'><path d='M22 0c13-1 24 9 24 22c0 13-10 24-23 24c-13 0-23-10-23-23c0-12 9-22 22-23z'/><path d='M40 40l22 24'/></g>
<g transform='translate(58 1262) rotate(10)'><path d='M4 0c5-1 9 3 9 8c0 5-4 8-9 8c-5 0-8-4-8-8c0-4 3-8 8-8zM30 26c5-1 9 3 9 8c0 5-4 8-9 8c-5 0-8-4-8-8c0-4 3-8 8-8zM34-2l-32 46'/></g>
"""


def _paper_css() -> str:
    enc = lambda svg: svg.replace("\n", "").replace("%", "%25").replace("<", "%3C").replace(">", "%3E").replace("#", "%23")
    sketches = enc("<svg xmlns='http://www.w3.org/2000/svg' width='150' height='1400' viewBox='0 0 150 1400' fill='none' "
                   "stroke='#0f172a' stroke-opacity='.08' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'>"
                   + _DOODLES + "</svg>")
    grain = enc("<svg xmlns='http://www.w3.org/2000/svg' width='220' height='220'><filter id='n'>"
                "<feTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='2' stitchTiles='stitch'/>"
                "<feColorMatrix values='0 0 0 0 .06  0 0 0 0 .09  0 0 0 0 .16  0 0 0 .04 0'/></filter>"
                "<rect width='100%' height='100%' filter='url(#n)'/></svg>")
    fade = "linear-gradient(transparent, #000 90px, #000 calc(100% - 90px), transparent)"
    return (
        '.stApp { background-image:radial-gradient(circle, rgba(15,23,42,.04) 1px, transparent 1.4px), '
        'url("data:image/svg+xml,' + grain + '"); background-size:24px 24px, 220px 220px; }\n'
        # margin sketches: only where a real margin exists, starting below the handwritten notes
        # .ld-page is the static site's column; .stMainBlockContainer is the same column in the Streamlit app
        '.ld-page, .stMainBlockContainer { --sk:clamp(56px, calc((100vw - 1170px) / 2), 150px); }\n'
        '.ld-page::before, .ld-page::after, .stMainBlockContainer::before, .stMainBlockContainer::after { content:""; display:none; position:absolute; top:760px; bottom:140px; width:var(--sk); '
        'pointer-events:none; background:url("data:image/svg+xml,' + sketches + '") repeat-y center top / var(--sk) auto; '
        f'-webkit-mask-image:{fade}; mask-image:{fade}; }}\n'
        '.ld-page::before, .stMainBlockContainer::before { left:calc(-12px - var(--sk)); } '
        '.ld-page::after, .stMainBlockContainer::after { right:calc(-12px - var(--sk)); transform:scaleX(-1); background-position:center 560px; }\n'
        '@media (min-width: 1260px) { .ld-page::before, .ld-page::after, .stMainBlockContainer::before, .stMainBlockContainer::after { display:block; } }'
    )


CSS = CSS.replace("</style>", _paper_css() + "\n</style>")

# The website's extra layer: tab bar, product cards, hero motion, scroll reveal, live strip. Written for the static
# page; the Streamlit app injects it too (plus src/app_ui.py for Streamlit's own widgets), so both read the same.
SITE_CSS = """
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


def icon(name: str) -> str:
    """An icon from ICONS, sized and coloured by the text around it."""
    return f'<em class="ld-ic ld-ic-{name}"></em>'


def esc(s) -> str:
    return html.escape("" if s is None else str(s)).replace("$", "&#36;")


def fmt(v, digits: int = 1) -> str:
    if v is None:
        return "—"
    return f"{v:.{digits}f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v)


def _tidy(s: str) -> str:
    s = re.sub(r"\s+", " ", (s or "").strip())
    return re.sub(r"(?<=[A-Za-z])['’]S\b", "'s", s.title()) if s and (s.islower() or s.isupper()) else s


# Hand-cleaned names for packs whose crowd-database name is wrong, misspelt or unreadable:
# (raw brand, raw name) -> (brand, product, full name)
NICE = {
    ("Britannia", "Good Day Cashew Cookies"): ("Britannia", "Good Day Cashew", "Britannia Good Day Cashew"),
    ("Paper Boat", "Swing+ Slurpy Mango"): ("Paper Boat", "Swing Mango Drink", "Paper Boat Swing Mango"),
    ("Parle", "Parle-G gold 75g"): ("Parle", "Parle-G Gold", "Parle-G Gold"),
    ("Maggi, Nestlé", "2 - Minute Noodles"): ("Maggi", "2-Minute Noodles", "Maggi 2-Minute Noodles"),
    ("Maggi", "Spicy Garlic 2 Minute Noodles"): ("Maggi", "Spicy Garlic Noodles", "Maggi Spicy Garlic Noodles"),
    ("Nestlé", "KitKat Chunky Caramel"): ("KitKat", "Chunky Caramel", "KitKat Chunky Caramel"),
    ("KitKat, Nestle nutrition", "Kitkat mini chocolate coated wafer"): ("KitKat", "Mini", "KitKat Mini"),
    ("Pepsico", "Mirinda"): ("PepsiCo", "Mirinda", "Mirinda"),
    ("Coca cola, Sprite", "Sprite"): ("Coca-Cola", "Sprite", "Sprite"),
    ("The Coca-Cola Company, कोका कोला क", "Sprite Lemon Lime flv Coke Brand 2ltr"): ("Coca-Cola", "Sprite Lemon-Lime (2 L)", "Sprite Lemon-Lime (2 L)"),
    ("Lay's", "PEPSICO."): ("Lay's", "Potato Chips", "Lay's Potato Chips"),
    ("WAIWAI", "WAI WAI"): ("Wai Wai", "Instant Noodles", "Wai Wai Noodles"),
    ("Nissin, Top Ramen", "top ramn"): ("Nissin", "Top Ramen Noodles", "Top Ramen Noodles"),
    ("Samyang", "3x spicy noddles"): ("Samyang", "3x Spicy Noodles", "Samyang 3x Spicy Noodles"),
    ("Kissan", "kissan fresh Tamato"): ("Kissan", "Fresh Tomato Ketchup", "Kissan Fresh Tomato Ketchup"),
    ("what's up", "what's up eye health zeaxanthin & lutein gummies"): ("What's Up", "Eye Health Gummies", "What's Up Eye Health Gummies"),
    ("Organic peanut butter Creamy", "24 Mantra Organic"): ("24 Mantra Organic", "Peanut Butter (Creamy)", "24 Mantra Peanut Butter"),
    ("Mother Diary", "Classic Curd"): ("Mother Dairy", "Classic Curd", "Mother Dairy Classic Curd"),
    ("Mother Diary", "White Bread"): ("Mother Dairy", "White Bread", "Mother Dairy White Bread"),
    ("Boni", "Mélange de bonbons"): ("Boni", "Mixed Candies", "Boni Mixed Candies"),
    ("Saffola", "Oodles Yummy masala ring noodles"): ("Saffola", "Oodles Ring Noodles", "Saffola Oodles"),
    ("Aashirvaad", "Aashirvaad Vermicilli"): ("Aashirvaad", "Vermicelli", "Aashirvaad Vermicelli"),
    ("Aashirvaad", "Multi -Millet Mix"): ("Aashirvaad", "Multi-Millet Mix", "Aashirvaad Multi-Millet Mix"),
    ("One Science", "ISO GOLD WHEY PROTEIN ISOLATE"): ("One Science", "ISO Gold Whey Protein", "One Science ISO Gold Whey"),
    ("BABU, Laxminarayan", "Lite Chiwda"): ("Laxminarayan", "Lite Chiwda", "Laxminarayan Lite Chiwda"),
    ("MTR", "Idli Karam Podi"): ("MTR", "Idli Karam Podi", "MTR Idli Karam Podi"),
    ("4700BC", "instant popcorn"): ("4700BC", "Instant Popcorn", "4700BC Instant Popcorn"),
}
_SMALL = {"and", "of", "the", "with", "for", "in", "de", "flv"}


def _smart(s: str) -> str:
    """Capitalise stray lowercase words and calm SHOUTED ones; short acronyms (MTR, TGF) stay."""
    out = []
    for i, w in enumerate(s.split()):
        if w.islower() and (w not in _SMALL or i == 0):
            w = w[:1].upper() + w[1:]
        elif w.isupper() and w.isalpha() and len(w) > 4:
            w = w.capitalize()
        out.append(w)
    return " ".join(out)


def display_name(brand: str | None, name: str | None) -> tuple[str, str]:
    """(brand, product name) with crowd-database noise removed: duplicate brand, pack size, ALL CAPS, lowercase."""
    if (brand, name) in NICE:
        return NICE[(brand, name)][:2]
    b = _smart(_tidy((brand or "").split(",")[0]))
    n = _smart(_tidy(re.sub(r"\s*\d+(\.\d+)?\s*(g|gm|kg|ml|l|ltr)\.?$", "", name or "", flags=re.I)))
    if not n:
        return "", b or "Unnamed product"
    if b and n.lower().startswith(b.lower() + " "):
        n = n[len(b):].strip()
    return b, n


def full_name(brand: str | None, name: str | None) -> str:
    if (brand, name) in NICE:
        return NICE[(brand, name)][2]
    b, n = display_name(brand, name)
    return n if not b or b.lower() in n.lower() else f"{b} {n}"


# ---------------------------------------------------------------------------------------------
# hero and picker
# ---------------------------------------------------------------------------------------------

def bi(en: str, hi: str) -> str:
    """English and Hindi side by side; the page shows one (see .hi in the CSS). Both parts must already be HTML-safe."""
    return f'<span class="en">{en}</span><span class="hi" lang="hi">{hi}</span>'


def hero(cta: bool = False) -> str:
    """Headline, one line, one button. `cta` adds the buttons (the static site has in-page anchors, Streamlit does not)."""
    buttons = ('<div class="ld-ctas"><a class="ld-cta" href="#packs">Check a pack ↓</a>'
               '<a class="ld-cta ghost" href="#how">How we know</a></div>') if cta else ""
    pack = (
        '<div class="ld-pack" aria-hidden="true">'
        '<div class="ld-face front"><span class="tag">FRONT</span><div class="br">CRUNCHY OATS</div><div class="hl">HEALTHY</div>'
        '<span class="ck">✓ High protein</span><span class="ck">✓ No added sugar</span><span class="ck">✓ Real fruit</span>'
        '<div class="sun"></div></div>'
        '<div class="ld-face back"><span class="tag">BACK</span><div class="h">INGREDIENTS</div>'
        '<div class="t">Oats, <mark>sugar</mark>, <mark>glucose syrup</mark>, palm oil, <mark>maltodextrin</mark>, '
        '<mark>invert syrup</mark>, salt</div>'
        '<div class="cb"><i></i><i></i><i></i><i></i><i></i></div><div class="eq">= 5 spoons of sugar</div></div>'
        '<div class="ld-pack-cap">Same pack. Two stories.</div></div>'
    )
    return (
        '<div class="ld-hero"><div class="ld-hero-grid"><div>'
        '<span class="ld-badge">Is this pack healthy?</span>'
        '<h1><span class="ld-ln"><span class="ld-rot">Healthy</span> on the front.</span><br><span class="ld-ln"><em class="ld-rot2">Sugar</em> on the back.</span></h1>'
        '<p class="sub">Turn the pack over. This reads the <b>ingredient list</b> and the nutrition table on the back '
        'and gives one answer: <b>healthy, or not healthy</b>.</p>'
        + buttons +
        '<div class="ld-proof"><b>100</b> Indian packs checked · only <b>11</b> came out healthy · '
        '<b>87%</b> accurate when reading photos</div>'
        '</div>' + pack + '</div></div>'
    )


def _tiles(tiles: list) -> str:
    return "".join(f'<div class="ld-ab"><div class="ic">{i}</div><b>{esc(t)}</b><ul>'
                   + "".join(f"<li>{p}</li>" for p in pts) + "</ul></div>" for i, t, pts in tiles)


def about() -> str:
    """The project in three boxes: problem, product, proof. Method and credits live in method(), lower down."""
    tiles = [
        (icon("target"), "The problem", [
            "The front says “healthy”, “multigrain”, “no added sugar”",
            "The back says maida, palm oil and sugar under 3 names",
            "Nobody has time to read the back in a shop",
            "<b>So nobody knows if the pack is healthy.</b>"]),
        (icon("phone"), "What it does", [
            "Reads the back of the pack: ingredient list and nutrition table",
            "Runs 4 checks: sugar, fat and salt, ingredients, good stuff",
            "Each check gets a green, yellow or red light",
            "<b>One answer: healthy, okay sometimes, or not healthy</b>"]),
        (icon("bars"), "The proof", [
            "100 Indian packs checked",
            "Only <b>11 came out healthy</b>; 42 are not healthy",
            "Photo reading: <b>87% accurate</b>, 96% on clean photos",
            "Same pack, same answer, every time"]),
    ]
    return (f'<div class="ld-card ld-about"><div class="ld-h2">The whole project in 30 seconds</div>'
            f'<div class="ld-h2-sub">Three boxes. Read left to right.</div><div class="ld-ab-grid">{_tiles(tiles)}</div></div>')


def method() -> str:
    """How we know: sources, mechanism, limits, credits. Sits at the bottom so the tool comes first."""
    tiles = [
        (icon("book"), "Where the rules come from", [
            "<b>FSSAI</b>, India's food regulator: Advertising &amp; Claims Regulations 2018, Labelling &amp; Display Regulations 2020",
            "<b>WHO</b>, the World Health Organization: under 25 g of added sugar a day (2015 guideline)",
            "Traffic-light cut-offs: the UK Food Standards Agency scheme, because India has not finalised its own",
            "Ingredient check: the NOVA markers of ultra-processed food; protein and fibre levels as FSSAI defines them"]),
        (icon("gear"), "How it works", [
            "AI only <b>reads</b> the pack",
            "The verdict comes from <b>written rules</b>, not from AI",
            "Four checks (sugar, fat and salt, ingredients, good stuff), each a light; the verdict <b>counts the lights</b>",
            "60+ names for sugar, 26 label tricks",
            "39 automated tests on the rules"]),
        (icon("alert"), "What it cannot do", [
            "Pack data comes from Open Food Facts, which anyone can edit, so it can be wrong",
            "Photo reading is 87% right, and less on blurry photos",
            "If a pack prints no serve size, we assume a typical one and say so",
            "This is not medical advice"]),
        (icon("user"), "About the project", [
            "Built by Om Rana as a product-management project",
            "Python, Streamlit, Claude / Gemini vision, Open Food Facts",
            "Pack data collected in October 2026"]),
    ]
    return (f'<div class="ld-card ld-about" id="how" style="margin-top:26px"><div class="ld-h2">How we know</div>'
            f'<div class="ld-h2-sub">Where the rules come from, how the tool decides, and what it cannot do</div>'
            f'<div class="ld-ab-grid two">{_tiles(tiles)}</div></div>')


INTROS = {
    "suspects": ("The usual suspects",
                 "Eight packs everyone buys. Tap one to see if it is healthy.",
                 "Start with Cadbury Shots. It is the worst of the lot.",
                 '<div class="ld-bigic">' + icon("package") + '</div>'),
    "barcode": ("Those 13 digits know everything",
                "The number under the black bars is the pack's ID. Type it, we fetch the label.",
                "Indian packs start with 890. Try 8901063139329 (Britannia Bourbon), or whatever is in your kitchen.",
                '<div class="ld-barcode"><div class="bars"></div><div class="num">8 901063 139329</div></div>'),
    "photo": ("Show us the back of the pack",
              "The ingredient list and the nutrition table. The AI reads them, the rules say healthy or not.",
              "Flat and bright works best. Crumpled packs and glare are our weak spot: 66% accuracy there, 96% on clean shots.",
              '<div class="ld-frames"><div>Front</div><div>Ingredients</div><div>Nutrition</div></div>'),
    "paste": ("No camera? Type it",
              "Copy what the pack says, as messy as you like. We sort it out.",
              "Claims, the ingredient list, the nutrition table and the serve size. Even one of these is a start.",
              '<div class="ld-typed">No added sugar. High protein.<br>Ingredients: Oats (40%), Dates…<br>Per 100 g: Sugars 22 g…</div>'),
    "faceoff": ("Face-off",
                "Two packs enter. One has less sugar. Settle the kitchen argument.",
                "Start with Mishti Doi vs Classic Dahi. Then try Mirinda vs Paper Boat.",
                '<div class="ld-vsbadge"><span>A</span><b>VS</b><span>B</span></div>'),
    "bigpicture": ("The big picture",
                   "We ran all 100 packs through the four health checks. Here is what came out.",
                   "Every number on this page is counted from the packs. Nothing is typed in by hand.",
                   '<div class="ld-bigic">' + icon("bars") + '</div>'),
    "airead": ("Watch the AI read a pack",
               "Real photos, the AI's real reading, checked number by number against the database.",
               "Recorded from the accuracy test: 300 photos, 87% of numbers right. 96% on clean photos, 66% on hard-to-read ones.",
               '<div class="ld-frames"><div>Front</div><div>Ingredients</div><div>Nutrition</div></div>'),
    "lineup": ("The full lineup",
               "All 100 packs we tested, A to Z. Find yours.",
               "Spoiler: Horlicks is 46% sugar. Parle-G is a quarter sugar. Maggi is a third of your day's salt.",
               '<div class="ld-bigic">' + icon("list") + '</div>'),
}


def intro(kind: str) -> str:
    title, line, tip, art = INTROS[kind]
    return (f'<div class="ld-intro"><div class="art">{art}</div><div>'
            f'<div class="t">{esc(title)}</div><div class="l">{esc(line)}</div>'
            f'<div class="tip"><b>Tip</b> {esc(tip)}</div></div></div>')


def marquee(items: list[tuple[str, str]]) -> str:
    """items: (headline, detail). Rendered twice so the CSS loop is seamless."""
    inner = "".join(f'<span><i>●</i><b>{esc(h)}</b> {esc(d)}</span>' for h, d in items)
    return f'<div class="ld-marq"><div>{inner}{inner}</div></div>'


def product_card(brand: str | None, name: str | None, img: str | None, sugar_100, is_liquid: bool,
                 selected: bool = False, ribbon: str | None = None, code: str | None = None) -> str:
    """`code` is written as data-code, so a script can find the card for a barcode (the live strip opens it)."""
    n = full_name(brand, name)
    pic = f'<img src="{esc(img)}" alt="">' if img else '<span style="font-size:40px;color:var(--faint)">' + icon("package") + '</span>'
    if sugar_100 is None:
        chip = '<span class="ld-chip grey">sugar not declared</span>'
    else:
        level = traffic("sugar", sugar_100, is_liquid)
        unit = "g / 100 ml" if is_liquid else "% sugar"
        val = f"{fmt(float(sugar_100))} {unit}" if is_liquid else f"{fmt(float(sugar_100))}{unit}"
        chip = f'<span class="ld-chip {level}">{esc(val)}</span>'
    rib = ""
    if ribbon:
        cls = {"MOST SUGAR": "", "BIGGEST TRICK": "gold", "LEAST SUGAR": "green"}.get(ribbon, "")
        rib = f'<span class="ld-ribbon {cls}">{esc(ribbon)}</span>'
    data = f' data-code="{esc(code)}"' if code else ""
    return f'<div class="ld-pcard{" on" if selected else ""}"{data}>{rib}<div class="img">{pic}</div><div class="nm">{esc(n)}</div>{chip}</div>'


def navbar(github: str, live: str | None = None, lang_toggle: bool = False) -> str:
    live_link = f'<a href="{esc(live)}" target="_blank">Try your own pack</a>' if live else ""
    lang = '<button class="ld-lang" id="ld-lang" title="Show the plain-words lines in Hindi">हिंदी</button>' if lang_toggle else ""
    return (f'<div class="ld-nav"><div class="logo"><i>{icon("search")}</i>Label Decoder</div>'
            f'<div class="links">{lang}<a href="#how">How we know</a>{live_link}<a href="{esc(github)}" target="_blank">GitHub</a>'
            f'<a class="cta" href="https://om-rana-portfolio.netlify.app" target="_blank">Made by Om Rana</a></div></div>')


def no_key_card() -> str:
    return ('<div class="ld-empty"><b>Photo reading is off on this copy</b> (it needs an AI key).<br>'
            'Pick one of <b>the usual suspects</b> or <b>scan a barcode</b>. Same results, no key needed.</div>')


def footer(github: str) -> str:
    return (f'<div class="ld-footer">Made by <b>Om Rana</b> · <a href="{esc(github)}" target="_blank">Code on GitHub</a><br>'
            'AI only reads the pack. The verdicts come from written rules: FSSAI (India\'s food regulator) and WHO (World Health Organization) sugar advice, '
            'so the same pack always gets the same answer. Not medical advice.</div>')


# ---------------------------------------------------------------------------------------------
# result
# ---------------------------------------------------------------------------------------------

def traffic(nutrient: str, v, is_liquid: bool) -> str:
    if v is None:
        return "grey"
    lo, hi = (FSA_DRINK if is_liquid else FSA_FOOD)[nutrient]
    v = float(v)
    return "green" if v <= lo else ("red" if v > hi else "amber")


def _lights(per100: dict, is_liquid: bool) -> dict:
    salt = per100.get("salt_g")
    if salt is None and per100.get("sodium_mg") is not None:
        salt = float(per100["sodium_mg"]) * 2.5 / 1000.0
    vals = {"sugar": per100.get("total_sugars_g"), "fat": per100.get("total_fat_g"),
            "satfat": per100.get("saturated_fat_g"), "salt": salt}
    return {k: (v, traffic(k, v, is_liquid)) for k, v in vals.items()}


def verdict(result: dict, lights: dict) -> tuple[str, str]:
    """The banner colour and word. It is the health verdict: four lights, counted (src/rules/health.py)."""
    h = result.get("health")
    if h:
        return ("amber" if h["color"] == "grey" else h["color"]), h["word"]
    high_flags = [f for f in result["flags"] if f["severity"] == "high"]
    reds = [k for k, (_, lvl) in lights.items() if lvl == "red"]
    if high_flags or lights["sugar"][1] == "red" or len(reds) >= 2:
        return "red", "Careful!"
    if reds or result["flags"] or lights["sugar"][1] == "amber":
        return "amber", "Okay, sometimes"
    if all(lvl == "grey" for _, lvl in lights.values()):
        return "amber", "Not enough info"
    return "green", "Good to go"


VERDICT_HI = {"Careful!": "संभलकर!", "Okay, sometimes": "कभी-कभी ठीक है", "Not enough info": "जानकारी कम है",
              "Good to go": "बेझिझक खाइए", "Not healthy": "सेहतमंद नहीं", "Healthy": "सेहतमंद"}


def _sugar_headline(result: dict, lights: dict, unit: str) -> tuple[str, str] | None:
    """The one-line sugar verdict as (English, Hindi), or None when sugar is not the story."""
    s = result["sugar"]
    pct = s["total_sugars_per_100"]
    if pct is None or lights["sugar"][1] == "green":
        return None
    pct, tsp = float(pct), s["teaspoons_total_per_serve"]
    if unit == "g":
        en, hi = (("Almost three-quarters of this pack is sugar.", "इस पैकेट का लगभग तीन-चौथाई हिस्सा चीनी है।") if pct >= 70 else
                  ("About half of this pack is sugar.", "इस पैकेट का लगभग आधा हिस्सा चीनी है।") if pct >= 45 else
                  ("A third of this pack is sugar.", "इस पैकेट का एक-तिहाई हिस्सा चीनी है।") if pct >= 30 else
                  ("A fifth of this pack is sugar.", "इस पैकेट का पाँचवाँ हिस्सा चीनी है।") if pct >= 18 else
                  (f"{fmt(pct)} g of sugar in every 100 g.", f"हर 100 ग्राम में {fmt(pct)} ग्राम चीनी।"))
        if tsp:
            en, hi = en + f" One serve = {tsp:.1f} spoons.", hi + f" एक सर्व = {tsp:.1f} चम्मच।"
        return en, hi
    if tsp:
        return (f"One {fmt(s['serving_g'])} ml serve = {tsp:.1f} spoons of sugar.",
                f"एक {fmt(s['serving_g'])} ml सर्व = {tsp:.1f} चम्मच चीनी।")
    return f"{fmt(pct)} g of sugar in every 100 ml.", f"हर 100 ml में {fmt(pct)} ग्राम चीनी।"


def _reasons(result: dict, lights: dict, unit: str) -> tuple[str, list[str]]:
    rank = result["consolidated_sugar"]
    names = {"sugar": "sugar", "fat": "fat", "satfat": "saturated fat", "salt": "salt"}
    out: list[str] = []
    pair = _sugar_headline(result, lights, unit)
    headline = pair[0] if pair else ""
    if rank.get("n_added_sugar_lines", 0) >= 2:
        out.append(f"Sugar hides under {rank['n_added_sugar_lines']} different names.")
    for c in result["claims"]:
        claim = c["claim_text"].strip().capitalize()
        if c["verdict"] == "fails":
            out.append(f"“{claim}” is not true.")
        elif c["verdict"] == "legal but misleading":
            out.append(f"“{claim}”: true on paper, not on your plate.")
    for k in ("salt", "satfat", "fat"):
        if lights[k][1] == "red":
            out.append(f"Lots of {names[k]}: {fmt(float(lights[k][0]))} g in 100 {unit}.")
    for f in result["flags"]:
        if f["severity"] == "high" and f["code"] not in ("SUGAR_SPLIT", "PER100_VS_SERVE", "CLAIM_FAILS"):
            out.append(SIMPLE.get(f["code"], f["title"] + "."))
    if not headline:
        headline = out.pop(0) if out else "Nothing sneaky on this label."
    return headline, out[:3]


# one plain-words line per trick code; the decoder's own detail stays underneath as "the small print"
SIMPLE = {
    "SUGAR_SPLIT": "Sugar is cut into pieces so it never looks like the #1 ingredient.",
    "NAS_SUBSTITUTE": "Says “no added sugar”, then adds sweet stuff like fruit syrup, honey or jaggery.",
    "NAS_HIGH_INTRINSIC": "“No added sugar” is true. But fruit sugar is still sugar to your body.",
    "SUGAR_FREE_POLYOL": "Sugar free, but sweet from polyols. Too many = upset tummy.",
    "SUGAR_FREE_SWEETENER": "The sweetness comes from artificial sweeteners.",
    "SUGAR_FREE_MALTODEXTRIN": "“Sugar free”, but has maltodextrin, which raises blood sugar even faster than sugar.",
    "PER100_VS_SERVE": "The claim is counted on 100 g. Your bite is much smaller.",
    "CLAIM_FAILS": "The claim does not meet the legal number.",
    "HALO_OVER_SUGAR": "Healthy words on the front. Sugar near the top of the list on the back.",
    "HEALTH_DRINK_SUGAR": "Sold as healthy. Mostly sugar.",
    "IMMUNITY_CLAIM": "“Immunity” here is a marketing word, not a proven claim.",
    "ENERGY_GROWTH_CLAIM": "“Energy” on a pack just means calories.",
    "NATURAL_WITH_ADDITIVES": "Says “natural”, but has added colours, flavours or preservatives.",
    "REAL_FRUIT_TRACE": "“Real fruit” is just a tiny pinch.",
    "REAL_FRUIT_NO_PCT": "“Real fruit”, but how much? The pack does not say.",
    "MULTIGRAIN_MAIDA": "Says multigrain. The #1 ingredient is maida.",
    "BAKED_STILL_FATTY": "Baked, yes. Still very oily.",
    "CHOLESTEROL_FREE_PLANT": "“Cholesterol free” is true for every plant food. Nothing special.",
    "NO_MSG_GLUTAMATE": "“No MSG”, but other ingredients do the same job.",
    "AS_PREPARED": "The numbers include the milk you add. The powder alone is mostly sugar.",
    "SERVING_TINY": "The “serve” is tiny, so every number looks small.",
    "WHO_LIMIT_BLOWN": "One serve = a whole day's sugar, or more.",
    "WHO_LIMIT_HALF": "One serve = half a day's sugar.",
    "SODIUM_HIGH": "A lot of salt in one serve.",
    "SAT_FAT_HIGH": "A big share of the calories come from saturated fat.",
    "TRANS_FAT": "Has trans fat, the worst kind of fat.",
}
SIMPLE_HI = {
    "SUGAR_SPLIT": "चीनी को टुकड़ों में बाँटा गया है ताकि वह सूची में सबसे ऊपर न दिखे।",
    "NAS_SUBSTITUTE": "लिखा है “no added sugar”, पर फल का सिरप, शहद या गुड़ जैसी मीठी चीज़ें डाली गई हैं।",
    "NAS_HIGH_INTRINSIC": "“No added sugar” सही है। पर फल की चीनी भी शरीर के लिए चीनी ही है।",
    "SUGAR_FREE_POLYOL": "शुगर-फ़्री है, पर मिठास पॉलिऑल से आती है। ज़्यादा खाने से पेट ख़राब हो सकता है।",
    "SUGAR_FREE_SWEETENER": "मिठास आर्टिफ़िशियल स्वीटनर से आती है।",
    "SUGAR_FREE_MALTODEXTRIN": "“Sugar free” लिखा है, पर इसमें माल्टोडेक्सट्रिन है, जो ब्लड शुगर चीनी से भी तेज़ बढ़ाता है।",
    "PER100_VS_SERVE": "दावा 100 ग्राम पर गिना गया है। आप उससे बहुत कम खाते हैं।",
    "CLAIM_FAILS": "दावा क़ानूनी सीमा पर खरा नहीं उतरता।",
    "HALO_OVER_SUGAR": "सामने सेहत की बातें। पीछे की सूची में चीनी सबसे ऊपर के पास।",
    "HEALTH_DRINK_SUGAR": "हेल्दी बताकर बेचा जाता है। ज़्यादातर चीनी है।",
    "IMMUNITY_CLAIM": "यहाँ “immunity” सिर्फ़ मार्केटिंग का शब्द है, साबित दावा नहीं।",
    "ENERGY_GROWTH_CLAIM": "पैकेट पर “energy” का मतलब बस कैलोरी है।",
    "NATURAL_WITH_ADDITIVES": "“Natural” लिखा है, पर रंग, फ़्लेवर या प्रिज़र्वेटिव मिलाए गए हैं।",
    "REAL_FRUIT_TRACE": "“Real fruit” बस नाम भर का है।",
    "REAL_FRUIT_NO_PCT": "“Real fruit” लिखा है, पर कितना? पैकेट नहीं बताता।",
    "MULTIGRAIN_MAIDA": "मल्टीग्रेन लिखा है। पर सबसे ज़्यादा मैदा है।",
    "BAKED_STILL_FATTY": "बेक्ड ज़रूर है। फिर भी बहुत तेल है।",
    "CHOLESTEROL_FREE_PLANT": "“Cholesterol free” हर पौधे से बनी चीज़ के लिए सच है। इसमें कुछ ख़ास नहीं।",
    "NO_MSG_GLUTAMATE": "“No MSG” लिखा है, पर दूसरी चीज़ें वही काम करती हैं।",
    "AS_PREPARED": "ये आँकड़े दूध मिलाने के बाद के हैं। अकेला पाउडर ज़्यादातर चीनी है।",
    "SERVING_TINY": "“एक सर्व” बहुत छोटा रखा गया है, इसलिए हर आँकड़ा छोटा दिखता है।",
    "WHO_LIMIT_BLOWN": "एक सर्व = पूरे दिन की चीनी, या उससे ज़्यादा।",
    "WHO_LIMIT_HALF": "एक सर्व = आधे दिन की चीनी।",
    "SODIUM_HIGH": "एक सर्व में बहुत नमक है।",
    "SAT_FAT_HIGH": "कैलोरी का बड़ा हिस्सा सैचुरेटेड फ़ैट से आता है।",
    "TRANS_FAT": "इसमें ट्रांस फ़ैट है, जो सबसे ख़राब फ़ैट है।",
}


def _trick_line(result: dict) -> tuple[str, str]:
    """The single most useful 'what is the catch' line as (English, Hindi). Inputs are escaped here."""
    for c in result["claims"]:
        claim = esc(c["claim_text"].strip().capitalize())
        if c["verdict"] == "fails":
            return f"“{claim}” is <b>not true</b>.", f"“{claim}” <b>सही नहीं है</b>।"
        if c["verdict"] == "legal but misleading":
            return (f"“{claim}” is <b>true on paper, not on your plate</b>.",
                    f"“{claim}” <b>कागज़ पर सही है, थाली में नहीं</b>।")
    n = result["consolidated_sugar"].get("n_added_sugar_lines", 0)
    if n >= 2:
        return f"Sugar hides under <b>{n} different names</b>.", f"चीनी <b>{n} अलग नामों</b> से छिपी है।"
    for f in result["flags"]:                       # already sorted, most serious first
        if f["code"] in SIMPLE and f["code"] not in ("SODIUM_HIGH", "SAT_FAT_HIGH", "WHO_LIMIT_HALF", "WHO_LIMIT_BLOWN"):
            return esc(SIMPLE[f["code"]]), esc(SIMPLE_HI.get(f["code"], SIMPLE[f["code"]]))
    return "<b>No label tricks</b> found.", "लेबल पर <b>कोई चालाकी नहीं</b> मिली।"


def three_things(result: dict, lights: dict) -> str:
    """The three facts worth knowing before anything else: sugar, the catch, fat and salt."""
    s = result["sugar"]
    unit = "ml" if result["product"]["is_liquid"] else "g"
    tsp = s["teaspoons_total_per_serve"]
    if tsp is None:
        one = ("The pack <b>does not print its sugar</b>.", "पैकेट पर <b>चीनी की मात्रा लिखी ही नहीं</b> है।")
    elif tsp < 0.25:
        one = ("<b>Almost no sugar</b> in one serve.", "एक सर्व में <b>लगभग कोई चीनी नहीं</b>।")
    else:
        lead = s["added_sugars_per_serve"] if s["added_sugars_per_serve"] is not None else s["total_sugars_per_serve"]
        pct = 100.0 * lead / WHO_FREE_SUGAR_5PCT_G if lead is not None else None
        en = f"<b>{tsp:.1f} spoons of sugar</b> in one serve ({fmt(s['serving_g'])} {unit})."
        hi = f"एक सर्व ({fmt(s['serving_g'])} {unit}) में <b>{tsp:.1f} चम्मच चीनी</b>।"
        if pct is not None and pct >= 10:
            en, hi = en + f" That is {pct:.0f}% of a day's limit.", hi + f" यानी दिन की सीमा का {pct:.0f}%।"
        one = (en, hi)

    en_names = {"fat": "fat", "satfat": "saturated fat", "salt": "salt"}
    hi_names = {"fat": "फ़ैट", "satfat": "सैचुरेटेड फ़ैट", "salt": "नमक"}
    keys = ("fat", "satfat", "salt")

    def listed(ks: list, names: dict, joiner: str) -> str:
        words = [names[k] for k in ks]
        return words[0] if len(words) == 1 else ", ".join(words[:-1]) + joiner + words[-1]

    reds = [k for k in keys if lights[k][1] == "red"]
    ambers = [k for k in keys if lights[k][1] == "amber"]
    if reds:
        three = (f"<b>High in {listed(reds, en_names, ' and ')}</b> (red light).",
                 f"<b>{listed(reds, hi_names, ' और ')} ज़्यादा</b> {'है' if len(reds) == 1 else 'हैं'} (लाल बत्ती)।")
    elif ambers:
        three = (f"<b>Medium on {listed(ambers, en_names, ' and ')}</b>. Fine sometimes.",
                 f"<b>{listed(ambers, hi_names, ' और ')} मध्यम</b> {'है' if len(ambers) == 1 else 'हैं'}। कभी-कभी ठीक।")
    elif all(lights[k][1] == "grey" for k in keys):
        three = ("The pack <b>does not print</b> its fat or salt.", "पैकेट पर फ़ैट या नमक की मात्रा <b>नहीं लिखी</b>।")
    else:
        three = ("<b>Fat and salt are both low</b> (green light).", "<b>फ़ैट और नमक दोनों कम</b> हैं (हरी बत्ती)।")

    rows = "".join(f'<div><i>{i}</i><span>{bi(en, hi)}</span></div>'
                   for i, (en, hi) in enumerate((one, _trick_line(result), three), 1))
    return (f'<div class="ld-card"><div class="ld-h2">{bi("3 things to know about this pack", "इस पैकेट की 3 ज़रूरी बातें")}</div>'
            f'<div class="ld-3">{rows}</div></div>')


def health_card(result: dict) -> str:
    """The four health checks as four tiles (light, headline, reasons as points), how the verdict was counted,
    and how far one serve goes."""
    h = result.get("health")
    if not h:
        return ""
    pill = {"red": ("RED", "लाल"), "amber": ("YELLOW", "पीला"), "green": ("GREEN", "हरा"), "grey": ("NO DATA", "जानकारी नहीं")}
    tiles = ""
    for c in h["checks"]:
        pts = "".join(f"<li>{bi(esc(en), esc(hi))}</li>" for en, hi in c.get("points") or [])
        tiles += (f'<div class="ld-hc-t {c["color"]}"><div class="top"><span>{bi(esc(c["name"]), esc(c["name_hi"]))}</span>'
                  f'<em>{bi(*pill[c["color"]])}</em></div>'
                  f'<div class="hd">{bi(esc(c["head"]), esc(c["head_hi"]))}</div>{f"<ul>{pts}</ul>" if pts else ""}</div>')
    seen = [c["color"] for c in h["checks"] if c["color"] != "grey"]
    tally_en = ", ".join(f"{seen.count(k)} {w}" for k, w in (("red", "red"), ("amber", "yellow"), ("green", "green")) if seen.count(k))
    tally_hi = ", ".join(f"{seen.count(k)} {w}" for k, w in (("red", "लाल"), ("amber", "पीला"), ("green", "हरा")) if seen.count(k))
    rule = {"red": ("Two or more reds = <b>Not healthy</b>.", "दो या ज़्यादा लाल = <b>सेहतमंद नहीं</b>।"),
            "amber": ("One red, or two or more yellows = <b>Okay, sometimes</b>.", "एक लाल, या दो या ज़्यादा पीले = <b>कभी-कभी ठीक है</b>।"),
            "green": ("No red and at most one yellow = <b>Healthy</b>.", "कोई लाल नहीं और ज़्यादा से ज़्यादा एक पीला = <b>सेहतमंद</b>।"),
            "grey": ("Too little is printed on the pack to give a verdict.", "पैकेट पर इतना कम लिखा है कि फ़ैसला नहीं हो सकता।")}[h["color"]]
    count = bi(f"This pack: {tally_en}. {rule[0]}", f"यह पैकेट: {tally_hi}। {rule[1]}") if seen else bi(rule[0], rule[1])
    return (f'<div class="ld-card ld-hc"><div class="ld-h2">{icon("lights")} {bi("Is it healthy? Four checks on the back of the pack", "क्या यह सेहतमंद है? पैकेट के पीछे की चार जाँच")}</div>'
            f'<div class="ld-h2-sub">{bi("Read from the ingredient list and the nutrition table. Each check gets a light, and the verdict only counts the lights.", "सामग्री की सूची और न्यूट्रिशन टेबल से पढ़ा गया। हर जाँच को एक बत्ती मिलती है, और फ़ैसला सिर्फ़ बत्तियाँ गिनकर होता है।")}</div>'
            f'<div class="ld-hc-grid">{tiles}</div><div class="ld-hc-rule">{count}</div>'
            f'<div class="ld-mean"><b>{bi("How much is fine:", "कितना ठीक है:")}</b> {bi(esc(h["how_much"]), esc(h["how_much_hi"]))}</div></div>')


def _ing_chips(label: dict, sugar_lines: set, flag: bool, limit: int = 14) -> tuple[str, int]:
    """The ingredient list as numbered chips, biggest first. Returns (html, how many top-level ingredients)."""
    groups: list[tuple[dict, list[str]]] = []          # each ingredient with whatever its brackets hold
    for it in label.get("ingredients") or []:
        if it.get("nested") and groups:
            groups[-1][1].append(it.get("name") or "")
        elif not it.get("nested") and (it.get("name") or "").strip():
            groups.append((it, [it.get("name") or ""]))
    chips = []
    for n, (it, texts) in enumerate(groups[:limit], 1):
        nm = _tidy(it.get("name") or "")
        nm = nm[:30].rstrip() + "…" if len(nm) > 32 else nm
        cls = ("sug" if (it.get("name") or "").strip().lower() in sugar_lines
               else "bad" if flag and ingredient_flag(" ; ".join(texts)) else "")
        pct = f' · {fmt(float(it["percent"]))}%' if it.get("percent") is not None else ""
        chips.append(f'<span class="{cls}"><b>{n}</b>{esc(nm)}{esc(pct)}</span>')
    more = f'<span><b>…</b>{len(groups) - limit} more</span>' if len(groups) > limit else ""
    return "".join(chips) + more, len(groups)


def top_card(label: dict, result: dict, img: str | None, lights: dict) -> str:
    p = result["product"]
    unit = "ml" if p["is_liquid"] else "g"
    brand, name = display_name(p.get("brand"), p.get("name"))
    color, word = verdict(result, lights)
    mark = icon({"red": "alert", "amber": "alert", "green": "check"}[color])
    tsp = result["sugar"]["teaspoons_total_per_serve"]
    spoons = (f'<b>{tsp:.1f}</b>{bi("spoons of sugar in one serve", "चम्मच चीनी, एक सर्व में")}' if tsp is not None
              else bi("Sugar is not printed on this pack", "पैकेट पर चीनी की मात्रा नहीं लिखी"))
    pair = _sugar_headline(result, lights, unit)
    if pair:
        headline = bi(esc(pair[0]), esc(pair[1]))
    else:
        en, hi = _trick_line(result)
        headline = bi(en, hi) if "No label tricks" not in en else bi("Nothing sneaky on this label.", "इस लेबल पर कोई चालाकी नहीं।")
    pic = f'<img src="{esc(img)}" alt="">' if img else '<span class="ph" style="color:var(--faint)">' + icon("package") + '</span>'
    serve = result["serving"]
    meta = (f"One serve = {fmt(serve['g'])} {unit}, the amount eaten in one go ({esc(serve['source'])})" if serve["g"]
            else "The pack gives no serve size")
    if label.get("barcode"):
        meta += f" · Barcode {esc(label['barcode'])}"
    plain = {"red": ("This is a treat, not food. Once in a while is fine.", "यह रोज़ का खाना नहीं, कभी-कभार की चीज़ है।"),
             "amber": ("Okay now and then. Not every day.", "कभी-कभी ठीक है। रोज़ नहीं।"),
             "green": ("Fine for every day.", "रोज़ खाने के लिए ठीक है।")}[color]
    if word == "Not enough info":
        plain = ("The pack prints too little to judge.", "पैकेट पर इतना कम लिखा है कि तय नहीं हो सकता।")
    seen = [c["color"] for c in (result.get("health") or {}).get("checks", []) if c["color"] != "grey"]
    tally = ""
    if seen:
        t_en = " · ".join(f"{seen.count(k)} {w}" for k, w in (("red", "red"), ("amber", "yellow"), ("green", "green")) if seen.count(k))
        t_hi = " · ".join(f"{seen.count(k)} {w}" for k, w in (("red", "लाल"), ("amber", "पीला"), ("green", "हरा")) if seen.count(k))
        tally = f'<div class="vt">{bi("4 health checks: " + t_en, "4 जाँच: " + t_hi)}</div>'
    return (f'<div class="ld-card ld-vcard"><div class="ld-vban {color}"><div><div class="v">{mark} {bi(word, VERDICT_HI.get(word, word))}</div>{tally}</div>'
            f'<div class="s">{spoons}</div></div>'
            f'<div class="ld-top"><div class="img">{pic}</div><div>'
            f'<div class="ld-brand">{esc(brand)}</div><div class="ld-name">{esc(name)}</div>'
            f'<div class="ld-headline" style="margin-top:6px">{headline}</div>'
            f'<div class="ld-mean"><b>{bi("In plain words:", "सीधी बात:")}</b> {bi(*plain)}</div>'
            f'<div class="ld-meta">{meta}</div></div></div></div>')


def sugar_cards(result: dict) -> str:
    s = result["sugar"]
    unit = "ml" if result["product"]["is_liquid"] else "g"
    tsp = s["teaspoons_total_per_serve"]
    if tsp is None:
        left = ('<div class="ld-card"><div class="ld-h2"><em class="ld-ic ld-ic-spoon"></em> How many spoons of sugar?</div>'
                '<div class="ld-h2-sub">The pack does not print its sugar, so we cannot count the spoons.</div></div>')
    else:
        full, part = int(tsp), tsp - int(tsp)
        shown = min(full, 20)
        cubes = '<div class="ld-cube"></div>' * shown
        if part >= 0.1 and full < 20:
            cubes += f'<div class="ld-cube part" style="--empty:{(1 - part) * 100:.0f}%"></div>'
        more = f'<span class="ld-note">+{full - 20} more</span>' if full > 20 else ""
        cola = s["total_sugars_per_serve"] / 35.0 if s["total_sugars_per_serve"] else 0   # a 330 ml cola can ≈ 35 g sugar
        compare = (f"Same as drinking <b>{cola:.1f} cans of cola</b>." if cola >= 0.95
                   else f"Same as drinking <b>{cola * 100:.0f}% of a cola can</b>." if cola >= 0.1
                   else "Almost no sugar at all.")
        left = (f'<div class="ld-card"><div class="ld-h2"><em class="ld-ic ld-ic-spoon"></em> Spoons of sugar in one serve</div>'
                f'<div class="ld-h2-sub">One serve = {fmt(s["serving_g"])} {unit}, the amount the pack says you eat in one go. Each cube = 1 teaspoon.</div>'
                f'<div class="ld-big">{tsp:.1f} <small>teaspoons</small></div>'
                f'<div class="ld-cubes">{cubes or "<span class=ld-note>less than a tenth of a teaspoon</span>"}{more}</div>'
                f'<div class="ld-mean">{compare}</div></div>')

    def bar(label: str, grams: float) -> str:
        pct = 100.0 * grams / WHO_FREE_SUGAR_5PCT_G
        col = "var(--green)" if pct < 25 else ("var(--amber)" if pct < 50 else "var(--red)")
        return (f'<div class="ld-note" style="margin-top:12px;color:var(--muted)"><b>{label}</b>: {fmt(grams)} g = {pct:.0f}% of the day</div>'
                f'<div class="ld-bar" style="margin-top:6px"><div style="width:{min(pct, 100):.0f}%;background:{col}"></div></div>')

    total, added = s["total_sugars_per_serve"], s["added_sugars_per_serve"]
    if total is None and added is None:
        right = ('<div class="ld-card"><div class="ld-h2"><em class="ld-ic ld-ic-calendar"></em> Your sugar budget for today</div>'
                 '<div class="ld-h2-sub">Not enough numbers on the pack to work this out.</div></div>')
    else:
        lead = added if added is not None else total
        pct = 100.0 * lead / WHO_FREE_SUGAR_5PCT_G
        col = "var(--green)" if pct < 25 else ("var(--amber)" if pct < 50 else "var(--red)")
        ring = f'<div class="r" style="--p:{min(pct, 100):.0f};--c:{col}" data-v="{pct:.0f}%"></div>'
        # the day's budget as 6 cubes (25 g ≈ 6 teaspoons); this serve fills them, extra cubes turn red
        budget_tsp = WHO_FREE_SUGAR_5PCT_G / TEASPOON_G
        used = lead / TEASPOON_G
        cubes = ""
        for i in range(6):
            fill = min(max(used - i, 0.0), 1.0)
            cubes += ('<div class="ld-cube"></div>' if fill >= 0.95 else
                      f'<div class="ld-cube part" style="--empty:{(1 - fill) * 100:.0f}%"></div>' if fill >= 0.1 else
                      '<div class="ld-cube empty"></div>')
        over = int(round(max(used - budget_tsp, 0)))
        cubes += '<div class="ld-cube over"></div>' * min(over, 8) + (f'<span class="ld-note">+{over - 8}</span>' if over > 8 else "")
        word = ("Fits easily" if pct < 25 else "A third of the day" if pct < 40 else "Half the day gone" if pct < 60
                else "Most of the day gone" if pct < 100 else "The whole day, in one serve")
        meaning = ("Plenty of room left today." if pct < 25 else
                   "One more sweet thing and you are done for the day." if pct < 60 else
                   "After this, no more sugar today." if pct < 100 else
                   "One serve is more than a whole day. The red cubes are the extra.")
        bars = ""
        if total is not None and added is not None and total - added >= 0.5:
            bars = bar("With milk and fruit sugar too", total)
        right = (f'<div class="ld-card"><div class="ld-h2"><em class="ld-ic ld-ic-calendar"></em> Your sugar budget for today</div>'
                 f'<div class="ld-h2-sub">The World Health Organization (WHO) says: at most 6 spoons of added sugar a day. The dashed cubes are your day.</div>'
                 f'<div class="ld-ring">{ring}<div><div style="font-size:19px;font-weight:800;color:var(--ink)">{word}</div>'
                 f'<div class="ld-note" style="margin-top:2px">of today\'s budget, in one serve</div></div></div>'
                 f'<div class="ld-budget">{cubes}</div>'
                 f'<div class="ld-mean">{meaning}</div>{bars}'
                 f'<div class="ld-note">Where the added-sugar number comes from: {esc(s["added_sugar_method"])}.</div></div>')
    return f'<div class="ld-grid2">{left}{right}</div>'


def rank_card(result: dict, all_sugar: list[float]) -> str:
    """Where this pack sits among every pack in the test set, by sugar per 100 g/ml."""
    me = result["sugar"]["total_sugars_per_100"]
    if me is None or len(all_sugar) < 10:
        return ""
    vals = sorted(float(v) for v in all_sugar)
    below = sum(1 for v in vals if v < float(me))
    top = max(vals) or 1.0
    # mark the bar whose value is closest to this pack
    idx = min(range(len(vals)), key=lambda i: abs(vals[i] - float(me)))
    # square-root scale: most packs sit under 10 g, the sweets go past 70 g
    bars = "".join(f'<i class="{"me" if i == idx else ""}" style="height:{max(4, 100 * (v / top) ** 0.5):.0f}%"></i>'
                   for i, v in enumerate(vals))
    n = len(vals)
    if below >= n * 0.8:
        above = n - below - 1
        line = (f"Sweeter than <b>{below} of {n}</b> packs. "
                + ("Nothing we checked is sweeter." if above <= 0 else f"Only {above} {'is' if above == 1 else 'are'} sweeter than this."))
    elif below <= n * 0.2:
        line = f"One of the <b>least sugary</b> packs. {n - below - 1} of {n} have more sugar."
    else:
        line = f"Middle of the pack: sweeter than <b>{below} of {n}</b>."
    unit = "ml" if result["product"]["is_liquid"] else "g"
    return (f'<div class="ld-card"><div class="ld-h2"><em class="ld-ic ld-ic-bars"></em> Versus {n} Indian packs</div>'
            f'<div class="ld-h2-sub">One bar = one pack. Tall = more sugar. The dark bar is this one.</div>'
            f'<div class="ld-dist">{bars}</div>'
            f'<div class="ld-dist-axis"><span>◀ least sugar ({fmt(vals[0])} g per 100 {unit})</span><span>most sugar ({fmt(vals[-1])} g) ▶</span></div>'
            f'<div class="ld-mean">{line}</div></div>')


def order_card(label: dict, result: dict) -> str:
    """The ingredient list as numbered chips: sugar lines lit up, combined-rank callout when split."""
    sugar_lines = {h["ingredient_line"].strip().lower() for h in result["sugar_lines"] if h["tier"] == "added"}
    chips, n_items = _ing_chips(label, sugar_lines, flag=True)
    if n_items < 3:
        return ""
    rank = result["consolidated_sugar"]
    call = ""
    if rank.get("n_added_sugar_lines", 0) >= 2 and rank.get("combined_rank_estimate"):
        call = (f'<div class="ld-callout">Join the {rank["n_added_sugar_lines"]} yellow pieces and sugar jumps to '
                f'<b>#{rank["combined_rank_estimate"]}</b>. Legal, but sneaky.</div>')
    return (f'<div class="ld-card"><div class="ld-h2"><em class="ld-ic ld-ic-list"></em> What\'s inside, biggest first</div>'
            f'<div class="ld-h2-sub">The law: heaviest ingredient first. #1 is most of the pack. '
            f'<b style="color:#b45309">Yellow</b> = sugar. <b style="color:var(--red)">Red</b> = flagged by the ingredient check.</div>'
            f'<div class="ld-order">{chips}</div>{call}</div>')


def compare_card(label: dict, result: dict, img: str | None, lights: dict, winner: bool) -> str:
    p = result["product"]
    name = full_name(p.get("brand"), p.get("name"))
    color, word = verdict(result, lights)
    mark = icon({"red": "alert", "amber": "alert", "green": "check"}[color])
    win = f'<div class=win>{icon("medal")} Less sugar</div>' if winner else "<div class=win>&nbsp;</div>"
    s = result["sugar"]
    tsp = s["teaspoons_total_per_serve"]
    unit = "ml" if p["is_liquid"] else "g"
    pic = f'<img src="{esc(img)}" alt="">' if img else '<span style="font-size:48px;color:var(--faint)">' + icon("package") + '</span>'
    labels = {"sugar": "Sugar", "fat": "Fat", "satfat": "Sat fat", "salt": "Salt"}
    mini = "".join(f'<div class="{lvl}"><b>{fmt(float(v)) if v is not None else "—"}</b>{labels[k]}</div>'
                   for k, (v, lvl) in lights.items())
    return (f'<div class="ld-cmp"><div class="img">{pic}</div><div class="nm">{esc(name)}</div>'
            f'<span class="ld-verdict {color}">{mark} {word}</span>'
            f'<div class="big">{f"{tsp:.1f}" if tsp is not None else "—"} <small>tsp sugar per {fmt(s["serving_g"])} {unit}</small></div>'
            f'<div class="mini">{mini}</div>'
            f'{win}</div>')


# ---------------------------------------------------------------------------------------------
# shareable image (PIL): one card for WhatsApp / LinkedIn
# ---------------------------------------------------------------------------------------------

def share_image(label: dict, result: dict, lights: dict) -> bytes:
    from io import BytesIO
    from PIL import Image, ImageDraw, ImageFont

    def font(size: int, bold: bool = True):
        names = (["arialbd.ttf", "Arial Bold.ttf", "DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
                 if bold else ["arial.ttf", "Arial.ttf", "DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"])
        for n in names:
            try:
                return ImageFont.truetype(n, size)
            except OSError:
                continue
        return ImageFont.load_default()

    W, H = 1080, 1080
    im = Image.new("RGB", (W, H), "#f4f6f9")
    d = ImageDraw.Draw(im)
    color, word = verdict(result, lights)
    hexes = {"red": "#dc2626", "amber": "#d97706", "green": "#16a34a"}
    d.rectangle([0, 0, W, 18], fill=hexes[color])
    p = result["product"]
    name = full_name(p.get("brand"), p.get("name"))
    d.text((70, 70), "INDIAN LABEL DECODER", font=font(26), fill="#4338ca")
    # wrap the name to two lines max
    words, lines, cur = name.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=font(72)) > W - 140 and cur:
            lines.append(cur); cur = w
        else:
            cur = t
    lines.append(cur)
    y = 120
    for ln in lines[:2]:
        d.text((70, y), ln, font=font(72), fill="#1c1917"); y += 84
    d.rounded_rectangle([70, y + 10, 70 + d.textlength(word, font=font(34)) + 60, y + 72], radius=31, fill=hexes[color])
    d.text((100, y + 22), word, font=font(34), fill="#ffffff")
    y += 120
    s = result["sugar"]
    tsp = s["teaspoons_total_per_serve"]
    unit = "ml" if p["is_liquid"] else "g"
    if tsp is not None:
        d.text((70, y), f"{tsp:.1f}", font=font(170), fill="#1c1917")
        d.text((70 + d.textlength(f"{tsp:.1f}", font=font(170)) + 24, y + 110), f"teaspoons of sugar\nin one {fmt(s['serving_g'])} {unit} serve",
               font=font(36, False), fill="#57534e")
        y += 215
        full, part = int(tsp), tsp - int(tsp)
        x = 70
        for i in range(min(full, 12)):
            d.rounded_rectangle([x, y, x + 62, y + 62], radius=12, fill="#f1f5f9", outline="#94a3b8", width=4); x += 76
        if part >= 0.1 and full < 12:
            d.rounded_rectangle([x, y, x + 62, y + 62], radius=12, fill="#f1f5f9", outline="#94a3b8", width=4)
            d.rectangle([x + 4 + 54 * part, y + 4, x + 58, y + 58], fill="#f4f6f9")
        y += 100
    bullets = []
    if s["total_sugars_per_100"] is not None:
        bullets.append(f"{fmt(float(s['total_sugars_per_100']))}% sugar by weight" if unit == "g"
                       else f"{fmt(float(s['total_sugars_per_100']))} g sugar per 100 ml")
    rank = result["consolidated_sugar"]
    if rank.get("n_added_sugar_lines", 0) >= 2:
        bullets.append(f"Sugar hides under {rank['n_added_sugar_lines']} names")
    for c in result["claims"]:
        if c["verdict"] in ("fails", "legal but misleading"):
            bullets.append(f"\"{c['claim_text'].capitalize()}\": true on paper, not on your plate")
    for k, nm in (("salt", "salt"), ("satfat", "saturated fat")):
        if lights[k][1] == "red":
            bullets.append(f"Lots of {nm}")
    for b in bullets[:4]:
        d.ellipse([70, y + 14, 86, y + 30], fill=hexes[color])
        d.text((104, y), b, font=font(34, False), fill="#1c1917"); y += 54
    d.line([70, H - 110, W - 70, H - 110], fill="#e7e5e4", width=2)
    d.text((70, H - 86), "Decoded with tested FSSAI rules · Built by Om Rana", font=font(26, False), fill="#a8a29e")
    buf = BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def lights_card(lights: dict, is_liquid: bool) -> str:
    unit = "100 ml" if is_liquid else "100 g"
    labels = {"sugar": "Sugar", "fat": "Fat", "satfat": "Saturated fat", "salt": "Salt"}
    word = {"red": "HIGH", "amber": "MEDIUM", "green": "LOW", "grey": "NOT ON PACK"}
    tiles = "".join(
        f'<div class="ld-light {lvl}"><div class="k">{labels[k]}</div>'
        f'<div class="v">{fmt(float(v)) + " g" if v is not None else "—"}</div><div class="l">{word[lvl]}</div></div>'
        for k, (v, lvl) in lights.items())
    reds = [labels[k].lower() for k, (_, lvl) in lights.items() if lvl == "red"]
    red_list = reds[0] if len(reds) == 1 else ", ".join(reds[:-1]) + " and " + reds[-1] if reds else ""
    meaning = ("Red = too much " + red_list + " in every bite."
               if reds else "No red. Nothing in the danger zone." if any(l != "grey" for _, l in lights.values())
               else "The pack does not print these numbers.")
    return (f'<div class="ld-card"><div class="ld-h2"><em class="ld-ic ld-ic-lights"></em> Traffic lights (per {unit})</div>'
            f'<div class="ld-h2-sub">Green = go · Yellow = sometimes · Red = careful. Same cut-offs the UK prints on pack fronts.</div>'
            f'<div class="ld-lights">{tiles}</div><div class="ld-mean">{meaning}</div>'
            f'<div class="ld-note" style="margin-top:10px"><b>Per {unit}</b> = in every {"100 millilitres of this drink" if is_liquid else "100 grams of this food"}. '
            f'<b>Saturated fat</b> = the kind of fat that raises cholesterol. <b>Salt</b> = too much raises blood pressure.</div></div>')


def flags_card(flags: list[dict]) -> str:
    if not flags:
        return ('<div class="ld-card"><div class="ld-h2"><em class="ld-ic ld-ic-wand"></em> Tricks on this pack</div>'
                '<div class="ld-h2-sub">No tricks found. The numbers above are the whole story.</div></div>')
    sev = {"high": "Big trick", "medium": "Watch out", "low": "Small thing"}
    items = "".join(
        f'<div class="ld-flag {f["severity"]}"><div class="t"><span class="ld-sev {f["severity"]}">{sev[f["severity"]]}</span>'
        f'{esc(f["title"])}</div><div class="d">{esc(SIMPLE.get(f["code"], f["detail"]))}</div>'
        f'<div class="r">Small print: {esc(f["detail"])}<br>The rule: {esc(f["rule_ref"])}</div></div>'
        for f in flags)
    return (f'<div class="ld-card"><div class="ld-h2"><em class="ld-ic ld-ic-wand"></em> Tricks on this pack</div>'
            f'<div class="ld-h2-sub">{len(flags)} thing{"s" if len(flags) != 1 else ""} that {"are" if len(flags) != 1 else "is"} legal, but can fool you</div>{items}</div>')


CLAIM_VERDICT = {
    "holds": ("green", icon("check") + " True"),
    "fails": ("red", icon("cross") + " Not true"),
    "legal but misleading": ("amber", icon("alert") + " True on paper, not on your plate"),
    "unverifiable": ("grey", icon("question") + " Can't check: the pack skips that number"),
}


def _claim_plain(c: dict, serving_g: float | None, unit: str) -> str:
    """One plain sentence per claim; the rule's own wording goes in the small print."""
    nutrient = c["claim_type"].split()[-1]
    a, t = c.get("actual_per_100"), c.get("threshold")
    if c["verdict"] == "legal but misleading" and c.get("per_serving_pct_rda") is not None and serving_g:
        return (f"On 100 {unit} the claim passes. In your {fmt(serving_g)} {unit} serve you get only "
                f"{c['per_serving_pct_rda']:.0f}% of a day's {nutrient}.")
    if c["verdict"] == "fails" and a is not None and t is not None:
        return f"The law needs {fmt(float(t))} per 100 {unit}. This pack has {fmt(float(a))}."
    if c["verdict"] == "holds" and a is not None:
        return f"Checked: {fmt(float(a))} per 100 {unit}. That passes."
    if c["verdict"] == "unverifiable":
        return f"The pack does not print its {nutrient} number, so nobody can check this."
    return c["explanation"]


def claims_card(claims: list[dict], serving_g: float | None, unit: str) -> str:
    if not claims:
        return ""
    rows = []
    vs = ""
    for c in claims:
        col, word = CLAIM_VERDICT.get(c["verdict"], ("grey", c["verdict"]))
        rows.append(f'<div class="ld-claim"><div class="says"><div class="lbl">Pack says</div>'
                    f'<div class="q">“{esc(_tidy(c["claim_text"]).capitalize())}”</div></div>'
                    f'<div><div class="lbl">Truth</div><div class="vd {col}">{word}</div>'
                    f'<div class="ex">{esc(_claim_plain(c, serving_g, unit))}</div>'
                    f'<div class="r" style="font-size:12px;color:var(--faint);margin-top:6px">Small print: {esc(c["explanation"])}</div></div></div>')
        if not vs and c["verdict"] == "legal but misleading" and c.get("per_serving_pct_rda") is not None and serving_g:
            vs = (f'<div class="ld-vs"><div class="box a"><small>The company counts</small><b>100 {unit}</b>'
                  f'<span>a big pile nobody eats at once</span></div><div class="mid">vs</div>'
                  f'<div class="box b"><small>You eat</small><b>{fmt(serving_g)} {unit}</b>'
                  f'<span>= only {c["per_serving_pct_rda"]:.0f}% of a day\'s {esc(c["claim_type"].split()[-1])}</span></div></div>'
                  f'<div class="ld-mean"><b>The trick:</b> big number on 100 {unit}, tiny bite on your plate.</div>')
    return (f'<div class="ld-card"><div class="ld-h2"><em class="ld-ic ld-ic-chat"></em> Pack says vs. truth</div>'
            f'<div class="ld-h2-sub">Every claim on the front, checked against the rules of FSSAI, India\'s food regulator</div>{"".join(rows)}{vs}</div>')


def _highlight(text: str, needles: list[str]) -> str:
    spans = []
    low = text.lower()
    for n in sorted({n.strip().lower() for n in needles if n and len(n.strip()) > 2}, key=len, reverse=True):
        for m in re.finditer(re.escape(n), low):
            if not any(a < m.end() and m.start() < b for a, b, _ in spans):
                spans.append((m.start(), m.end(), n))
    spans.sort()
    out, i = [], 0
    for a, b, _ in spans:
        out.append(esc(text[i:a]))
        out.append(f"<mark>{esc(text[a:b])}</mark>")
        i = b
    out.append(esc(text[i:]))
    return "".join(out)


def sugar_names_card(label: dict, result: dict) -> str:
    lines = result["sugar_lines"]
    text = label.get("ingredients_text") or ", ".join(i.get("name", "") for i in (label.get("ingredients") or []))
    if not lines and not text:
        return ""
    tier_word = {"added": "added sugar", "sugar_like": "acts like sugar", "sweetener": "sweetener"}
    seen, chips = set(), []
    for h in lines:
        key = (h["canonical"], h["tier"])
        if key in seen:
            continue
        seen.add(key)
        chips.append(f'<span class="ld-name-chip">{esc(_tidy(h["ingredient_line"])[:40])} <i>= {esc(tier_word.get(h["tier"], h["tier"]))}</i></span>')
    n_added = result["consolidated_sugar"].get("n_added_sugar_lines", 0)
    sub = (f"Sugar wears {n_added} costumes here. Yellow = sugar in disguise."
           if n_added >= 2 else "Yellow = sugar, even with a fancy name." if chips
           else "No sugar hiding in this list.")
    body = (f'<div class="ld-ing">{_highlight(text, [h["ingredient_line"] for h in lines])}</div>'
            if text else "")
    why = ('<div class="ld-mean"><b>Why split it?</b> Ingredients go heaviest first. Cut sugar into pieces '
           'and no piece has to be #1.</div>' if n_added >= 2 else "")
    return (f'<div class="ld-card"><div class="ld-h2"><em class="ld-ic ld-ic-eye"></em> Sugar\'s disguises</div><div class="ld-h2-sub">{sub}</div>'
            f'{"<div class=ld-names>" + "".join(chips) + "</div>" if chips else ""}{body}{why}</div>')


def honest_card(result: dict) -> str:
    if not result["honest_label"]:
        return ""
    return (f'<div class="ld-card"><div class="ld-h2"><em class="ld-ic ld-ic-check"></em> The honest label</div>'
            f'<div class="ld-h2-sub">If the pack had nothing to sell you</div>'
            f'<div class="ld-honest">{esc(result["honest_label"])}</div></div>')


# ---------------------------------------------------------------------------------------------
# dashboard: what the whole test set says
# ---------------------------------------------------------------------------------------------

TRICK_NAMES = {
    "SUGAR_SPLIT": "Sugar split into many names", "SAT_FAT_HIGH": "Heavy on saturated fat",
    "SODIUM_HIGH": "A lot of salt in one serve", "SERVING_TINY": "A tiny “serving size”",
    "WHO_LIMIT_HALF": "Half a day's sugar in one serve", "WHO_LIMIT_BLOWN": "A whole day's sugar in one serve",
    "TRANS_FAT": "Contains trans fat", "PER100_VS_SERVE": "Claim true only per 100 g",
    "NAS_SUBSTITUTE": "“No added sugar” with sweet substitutes", "NAS_HIGH_INTRINSIC": "“No added sugar” but still sugary",
    "CHOLESTEROL_FREE_PLANT": "“Cholesterol free” on a plant food", "CLAIM_FAILS": "Claim fails the legal test",
}


def dashboard(packs: list[tuple[dict, dict]]) -> str:
    """packs: (label, decoded result) for every pack in the test set. Every number is counted here, nothing typed in."""
    n = len(packs)
    verdicts = {"red": 0, "amber": 0, "green": 0}
    lights_count = {k: {"red": 0, "amber": 0, "green": 0, "grey": 0} for k in ("sugar", "fat", "satfat", "salt")}
    checks_count = {k: {"red": 0, "amber": 0, "green": 0, "grey": 0} for k in ("sugar", "fat_salt", "ingredients", "good")}
    tricks: dict[str, int] = {}
    split = half_day = any_trick = 0
    sweet, most_names = [], (0, "")
    for label, r in packs:
        liquid = r["product"]["is_liquid"]
        lights = _lights(label.get("per_100") or {}, liquid)
        verdicts[verdict(r, lights)[0]] += 1
        for k, (_, lvl) in lights.items():
            lights_count[k][lvl] += 1
        for c in (r.get("health") or {}).get("checks", []):
            checks_count[c["key"]][c["color"]] += 1
        for f in r["flags"]:
            tricks[f["code"]] = tricks.get(f["code"], 0) + 1
        any_trick += bool(r["flags"])
        names = r["consolidated_sugar"].get("n_added_sugar_lines", 0)
        split += names >= 2
        name = full_name(label.get("brand"), label.get("product_name"))
        if names > most_names[0]:
            most_names = (names, name)
        s = r["sugar"]
        lead = s["added_sugars_per_serve"] if s["added_sugars_per_serve"] is not None else s["total_sugars_per_serve"]
        half_day += lead is not None and lead >= WHO_FREE_SUGAR_5PCT_G / 2
        if s["total_sugars_per_100"] is not None and not liquid:
            sweet.append((float(s["total_sugars_per_100"]), name))
    declared = n - lights_count["sugar"]["grey"]
    sugar_red = lights_count["sugar"]["red"]

    kpis = (f'<div class="ld-kpis">'
            f'<div class="ld-kpi red"><b>{sugar_red}<small> of {declared}</small></b><span>packs are high in sugar (red light)</span></div>'
            f'<div class="ld-kpi amber"><b>{split}<small> of {n}</small></b><span>hide sugar under 2 or more names</span></div>'
            f'<div class="ld-kpi red"><b>{half_day}<small> of {n}</small></b><span>use up half a day’s sugar budget in one serve</span></div>'
            f'<div class="ld-kpi"><b>{any_trick}<small> of {n}</small></b><span>carry at least one label trick</span></div></div>')

    r_, a_, g_ = verdicts["red"], verdicts["amber"], verdicts["green"]
    p1, p2 = 100 * r_ / n, 100 * (r_ + a_) / n
    donut = (f'<div class="ld-card"><div class="ld-h2">The verdicts</div><div class="ld-h2-sub">How the {n} packs came out</div>'
             f'<div class="ld-donut-wrap"><div class="ld-donut" data-v="{n}" style="background:conic-gradient(var(--red) 0 {p1:.1f}%, var(--amber) {p1:.1f}% {p2:.1f}%, var(--green) {p2:.1f}% 100%)"></div>'
             f'<div class="ld-legend"><div><i style="background:var(--red)"></i><b>{r_}</b> Not healthy</div>'
             f'<div><i style="background:var(--amber)"></i><b>{a_}</b> Okay, sometimes</div>'
             f'<div><i style="background:var(--green)"></i><b>{g_}</b> Healthy</div></div></div>'
             f'<div class="ld-mean">Only <b>{g_} in {n}</b> packs came out healthy.</div></div>')

    labels = {"sugar": "Sugar", "fat_salt": "Fat and salt", "ingredients": "Ingredients", "good": "Good stuff"}
    rows = ""
    lights_count = checks_count
    for k, c in lights_count.items():
        tot = c["red"] + c["amber"] + c["green"] or 1
        seg = "".join(f'<i style="width:{100 * c[l] / tot:.1f}%;background:var(--{l})">{c[l] if c[l] / tot > .07 else ""}</i>'
                      for l in ("red", "amber", "green"))
        rows += f'<div class="ld-stackrow"><span>{labels[k]}</span><div class="ld-stack">{seg}</div></div>'
    worst = max(lights_count, key=lambda k: lights_count[k]["red"])
    stack = (f'<div class="ld-card"><div class="ld-h2">The four health checks, all packs</div>'
             f'<div class="ld-h2-sub">How many packs got red, yellow or green on each check</div>{rows}'
             f'<div class="ld-mean">The biggest problem is <b>{labels[worst].lower()}</b>: {lights_count[worst]["red"]} packs are in the red.</div></div>')

    sweet.sort(reverse=True)
    bars = "".join(f'<div class="ld-hrow"><span class="n" title="{esc(nm)}">{esc(" ".join(nm.split()[:4]))}</span><div class="t"><i style="width:{v:.0f}%;background:var(--red)"></i></div>'
                   f'<span class="v">{fmt(v)}%</span></div>' for v, nm in sweet[:10])
    sweetest = (f'<div class="ld-card"><div class="ld-h2">The 10 sweetest packs</div>'
                f'<div class="ld-h2-sub">Sugar as a share of the pack’s weight</div>{bars}</div>')

    tr = sorted(tricks.items(), key=lambda kv: -kv[1])[:7]
    mx = tr[0][1] if tr else 1
    tbars = "".join(f'<div class="ld-hrow wide"><span class="n">{esc(TRICK_NAMES.get(c, c.replace("_", " ").capitalize()))}</span>'
                    f'<div class="t"><i style="width:{100 * v / mx:.0f}%;background:var(--amber)"></i></div><span class="v">{v}</span></div>'
                    for c, v in tr)
    common = (f'<div class="ld-card"><div class="ld-h2">The most common tricks</div>'
              f'<div class="ld-h2-sub">How many of the {n} packs do each one</div>{tbars}'
              f'<div class="ld-mean">Record holder: <b>{esc(most_names[1])}</b> lists a form of sugar <b>{most_names[0]} separate times</b> in its ingredients.</div></div>')

    share = r_ / n
    frac = min(((1 / 4, "1 in 4"), (1 / 3, "1 in 3"), (1 / 2, "1 in 2"), (2 / 3, "2 in 3"), (3 / 4, "3 in 4")),
               key=lambda f: abs(f[0] - share))
    who = f"About {frac[1]} packs" if abs(frac[0] - share) <= 0.06 else f"{r_} of {n} packs"
    lead = (f'<div class="ld-lead"><div class="big">{who} came out as <em>“Not healthy”</em></div>'
            f'<div class="sm">That is {r_} of the {n} packs we checked. Only {g_} came out healthy. The charts below show why.</div></div>')
    return lead + kpis + f'<div class="ld-grid2">{donut}{stack}</div><div class="ld-grid2" style="margin-top:14px">{sweetest}{common}</div>'


# ---------------------------------------------------------------------------------------------
# AI replay: a recorded photo reading, checked field by field
# ---------------------------------------------------------------------------------------------

READ_FIELDS = [("energy_kcal", "Energy", "kcal"), ("protein_g", "Protein", "g"), ("carbohydrate_g", "Carbs", "g"),
               ("total_sugars_g", "Sugar", "g"), ("total_fat_g", "Fat", "g"), ("saturated_fat_g", "Saturated fat", "g"),
               ("sodium_mg", "Sodium", "mg"), ("dietary_fibre_g", "Fibre", "g")]


def read_check(pred: dict, ref: dict) -> list[tuple]:
    """(field, unit, AI value, database value, match?) with the eval's own tolerance: max(0.5, 10%)."""
    pp, rp = pred.get("per_100") or {}, dict(ref.get("per_100") or {})
    if rp.get("sodium_mg") is None and rp.get("salt_g") is not None:
        rp["sodium_mg"] = float(rp["salt_g"]) * 400.0
    out = []
    for key, name, unit in READ_FIELDS:
        a, b = pp.get(key), rp.get(key)
        ok = None if a is None or b is None else abs(float(a) - float(b)) <= max(0.5, 0.1 * abs(float(b)))
        out.append((name, unit, a, b, ok))
    return out


def replay_card(name: str, imgs: dict, checks: list, pred: dict, summary: str | None = None) -> str:
    pics = "".join(f'<figure><img src="{esc(imgs[k])}" alt=""><figcaption>{k}</figcaption></figure>'
                   for k in ("front", "ingredients", "nutrition") if imgs.get(k))
    scored = [c for c in checks if c[4] is not None]
    good = sum(1 for c in scored if c[4])
    rows = ""
    for field, unit, a, b, ok in checks:
        if a is None and b is None:
            continue
        mark = ('<span class="ok">✓ match</span>' if ok else '<span class="no">≠ differs</span>' if ok is False
                else '<span style="color:var(--faint)">nothing to compare</span>')
        rows += (f'<tr class="{"bad" if ok is False else ""}"><td>{field}</td>'
                 f'<td class="ai">{fmt(float(a)) + " " + unit if a is not None else "not found"}</td>'
                 f'<td>{fmt(float(b)) + " " + unit if b is not None else "—"}</td><td>{mark}</td></tr>')
    leg = {"good": "clean photos", "partial": "some glare or blur", "poor": "hard to read"}.get(pred.get("legibility"), "")
    note = (pred.get("notes") or "").strip()
    note = note[:260].rsplit(" ", 1)[0] + "…" if len(note) > 260 else note
    summary = summary or (f"The AI got <b>{good} of {len(scored)}</b> numbers right on this pack." if good == len(scored)
               else f"The AI got only <b>{good} of {len(scored)}</b> numbers right here. This is why the app warns you when a photo is hard to read.")
    note_html = f'<div class="ld-note" style="margin-top:10px"><b>The AI’s own note:</b> {esc(note)}</div>' if note else ""
    return (f'<div class="ld-card"><div class="ld-flow"><span>1</span>The photos it was given</div>'
            f'<div class="ld-h2-sub">{esc(name)} · {esc(leg)}</div><div class="ld-photos">{pics}</div>'
            f'<div class="ld-flow"><span>2</span>What the AI read, checked against the database</div>'
            f'<table class="ld-read"><tr><th>Per 100 g</th><th>AI read</th><th>Database says</th><th></th></tr>{rows}</table>'
            f'<div class="ld-mean">{summary}</div>{note_html}'
            f'<div class="ld-flow"><span>3</span>The verdict, worked out from what the AI read</div></div>')
