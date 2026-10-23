"""
Presentation layer for the Streamlit app: CSS and HTML builders.

Nothing here judges a label. Every number comes from decode_label(); this module only decides
how to show it. The one piece of logic is the traffic light, which uses the UK FSA
front-of-pack thresholds (India has no final FOP standard yet) and is labelled as such.
"""

from __future__ import annotations

import html
import re

from src.rules.serving import TEASPOON_G, WHO_FREE_SUGAR_5PCT_G

# UK FSA front-of-pack thresholds per 100 g (food) / per 100 ml (drinks): (low <=, high >)
FSA_FOOD = {"sugar": (5.0, 22.5), "fat": (3.0, 17.5), "satfat": (1.5, 5.0), "salt": (0.3, 1.5)}
FSA_DRINK = {"sugar": (2.5, 11.25), "fat": (1.5, 8.75), "satfat": (0.75, 2.5), "salt": (0.3, 0.75)}

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Outfit:wght@600;700;800;900&display=swap');
:root{
  --ink:#1c1917; --muted:#57534e; --faint:#a8a29e; --line:#e7e5e4; --card:#ffffff; --bg:#faf7f2;
  --red:#dc2626; --red-bg:#fef2f2; --amber:#d97706; --amber-bg:#fffbeb; --green:#16a34a; --green-bg:#f0fdf4;
  --brand:#ea580c; --brand-bg:#fff7ed; --sugar:#fde68a;
}
html, body, .stApp, .stApp p, .stApp label, .stApp summary, button, input, textarea { font-family:'Inter',system-ui,sans-serif !important; }
[data-testid="stIconMaterial"] { font-family:'Material Symbols Rounded' !important; }
.stApp { background:var(--bg);
  background-image:radial-gradient(circle at 12% 0%, #ffedd5 0, transparent 38%), radial-gradient(circle at 95% 10%, #fef3c7 0, transparent 30%); }
.block-container { max-width:1080px; padding-top:0.6rem; padding-bottom:3rem; }
#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"] { display:none !important; }
header[data-testid="stHeader"] { background:transparent; height:0; }
.ld-h2, .ld-name, .ld-hero h1, .ld-big, .ld-cmp .nm, .ld-cmp .big, .ld-stat b { font-family:'Outfit','Inter',sans-serif !important; }

/* top bar */
.ld-nav { position:sticky; top:0; z-index:50; display:flex; align-items:center; justify-content:space-between; gap:12px;
  background:rgba(250,247,242,.85); backdrop-filter:blur(10px); border:1px solid var(--line); border-radius:14px;
  padding:10px 16px; margin:4px 0 16px; box-shadow:0 6px 20px rgba(28,25,23,.05); }
.ld-nav .logo { display:flex; align-items:center; gap:10px; font-family:'Outfit',sans-serif; font-weight:800; font-size:18px; color:var(--ink); }
.ld-nav .logo i { font-style:normal; display:grid; place-items:center; width:34px; height:34px; border-radius:10px; background:linear-gradient(135deg,#f97316,#f59e0b); color:#fff; font-size:18px; box-shadow:0 4px 10px rgba(249,115,22,.35); }
.ld-nav .links { display:flex; gap:8px; align-items:center; }
.ld-nav a { text-decoration:none; font-weight:600; font-size:13.5px; color:var(--muted); padding:7px 12px; border-radius:999px; border:1px solid transparent; }
.ld-nav a:hover { background:#fff; border-color:var(--line); color:var(--ink); }
.ld-nav a.cta { background:var(--ink); color:#fff; }
.ld-nav a.cta:hover { background:#292524; border-color:transparent; color:#fff; }

/* tabs -> pill segmented control */
.stTabs [data-baseweb="tab-list"] { gap:6px; border-bottom:none; flex-wrap:wrap; background:#fff; border:1px solid var(--line); border-radius:999px; padding:5px; width:fit-content; max-width:100%; }
.stTabs [data-baseweb="tab"] { padding:8px 16px; border-radius:999px; font-weight:600; color:var(--muted); transition:all .15s; }
.stTabs [data-baseweb="tab"]:hover { background:#fafaf9; color:var(--ink); }
.stTabs [aria-selected="true"] { color:#fff !important; background:linear-gradient(135deg,#f97316,#ea580c); box-shadow:0 4px 12px rgba(234,88,12,.3); }
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] { display:none; }
.stTabs [data-baseweb="tab-panel"] { padding-top:18px; }

/* streamlit widgets */
.stButton button, .stDownloadButton button { border-radius:999px; font-weight:700; border:1px solid var(--line); transition:all .15s; }
.stButton button:hover, .stDownloadButton button:hover { transform:translateY(-1px); border-color:#fdba74; color:var(--brand); }
.stButton button[kind="primary"], .stDownloadButton button[kind="primary"] { background:linear-gradient(135deg,#f97316,#ea580c); border:none; color:#fff; box-shadow:0 6px 16px rgba(234,88,12,.3); }
.stButton button[kind="primary"]:hover { color:#fff; box-shadow:0 8px 20px rgba(234,88,12,.4); }
.stTextInput input, .stTextArea textarea { border-radius:14px !important; border:1.5px solid var(--line) !important; background:#fff !important; font-size:15px; padding:12px 14px; }
.stTextInput input:focus, .stTextArea textarea:focus { border-color:var(--brand) !important; box-shadow:0 0 0 4px rgba(249,115,22,.15) !important; }
[data-baseweb="select"] > div { border-radius:14px !important; border:1.5px solid var(--line) !important; background:#fff !important; }
[data-testid="stFileUploader"] section { border:2px dashed #fdba74; border-radius:18px; background:#fff; }
[data-testid="stExpander"] { border:1px solid var(--line); border-radius:14px; background:#fff; }
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"] .ld-pcard) {
  background:var(--card); border-radius:18px !important; border:1px solid var(--line) !important; }
[data-testid="stVerticalBlockBorderWrapper"]:has(.ld-pcard.on) { border-color:#fb923c !important; box-shadow:0 0 0 4px rgba(249,115,22,.15), 0 12px 28px rgba(234,88,12,.12) !important; }
.ld-ribbon { position:absolute; top:10px; left:-6px; background:linear-gradient(135deg,#dc2626,#ef4444); color:#fff; font-size:11px; font-weight:800; letter-spacing:.04em; padding:4px 10px; border-radius:0 999px 999px 0; box-shadow:0 3px 8px rgba(220,38,38,.3); }
.ld-ribbon.gold { background:linear-gradient(135deg,#d97706,#f59e0b); box-shadow:0 3px 8px rgba(217,119,6,.3); }
.ld-ribbon.green { background:linear-gradient(135deg,#15803d,#22c55e); box-shadow:0 3px 8px rgba(21,128,61,.3); }

/* hero */
.ld-hero { position:relative; overflow:hidden; background:linear-gradient(135deg,#fff7ed 0%,#fffbeb 55%,#f0fdf4 100%); border:1px solid #fed7aa;
  border-radius:24px; padding:34px 34px 28px; margin-bottom:18px; box-shadow:0 20px 50px rgba(234,88,12,.08); }
.ld-hero::before { content:"🍪 🥤 🍫 🍬 🧃 🍩"; position:absolute; right:-10px; top:-18px; font-size:64px; letter-spacing:18px; opacity:.13; transform:rotate(-8deg); pointer-events:none; }
.ld-hero::after { content:""; position:absolute; width:320px; height:320px; right:-120px; bottom:-160px; border-radius:50%; background:radial-gradient(circle,#fed7aa 0,transparent 70%); opacity:.7; pointer-events:none; }
.ld-hero > * { position:relative; z-index:1; }
.ld-hero h1 em { background:linear-gradient(90deg,#ea580c,#f59e0b); -webkit-background-clip:text; background-clip:text; color:transparent; }
.ld-badge { display:inline-block; font-size:12px; font-weight:700; letter-spacing:.04em; text-transform:uppercase;
  color:var(--brand); background:#fff; border:1px solid #fed7aa; border-radius:999px; padding:4px 12px; }
.ld-hero h1 { font-size:44px; line-height:1.08; font-weight:800; color:var(--ink); margin:14px 0 10px; letter-spacing:-.02em; padding:0; }
.ld-hero h1 em { font-style:normal; color:var(--brand); }
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
.ld-ab .ic { font-size:24px; line-height:1; margin-bottom:8px; }
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
.ld-vs .box.a { background:#f5f5f4; } .ld-vs .box.b { background:var(--brand-bg); border:1px solid #fed7aa; }
.ld-vs .box small { display:block; font-size:12px; font-weight:700; letter-spacing:.05em; text-transform:uppercase; color:var(--faint); }
.ld-vs .box b { display:block; font-size:26px; color:var(--ink); margin:4px 0; }
.ld-vs .box span { font-size:13px; color:var(--muted); }
.ld-vs .mid { font-size:22px; font-weight:800; color:var(--faint); }
.ld-stat { background:#fff; border:1px solid var(--line); border-radius:14px; padding:12px 14px; }
.ld-stat b { display:block; font-size:24px; font-weight:800; color:var(--ink); }
.ld-stat span { font-size:13px; color:var(--muted); }

/* marquee of findings under the hero */
.ld-marq { overflow:hidden; white-space:nowrap; border-top:1px solid #fed7aa; border-bottom:1px solid #fed7aa; background:#fff; margin:-6px 0 18px; border-radius:12px; }
.ld-marq div { display:inline-block; padding:10px 0; animation:ld-scroll 45s linear infinite; }
.ld-marq span { display:inline-block; margin:0 22px; font-size:14px; font-weight:600; color:var(--muted); }
.ld-marq span b { color:var(--ink); } .ld-marq span i { font-style:normal; color:var(--brand); margin-right:6px; }
@keyframes ld-scroll { from { transform:translateX(0); } to { transform:translateX(-50%); } }

/* per-tab intro strip */
.ld-intro { display:grid; grid-template-columns:150px 1fr; gap:18px; align-items:center; background:#fff; border:1px solid var(--line);
  border-radius:18px; padding:16px 20px; margin:0 0 16px; animation:ld-in .35s ease both; }
.ld-intro .art { display:flex; align-items:center; justify-content:center; height:96px; background:linear-gradient(135deg,#fff7ed,#fffbeb); border-radius:14px; }
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
.ld-frames div { width:38px; height:54px; border:2px dashed #fb923c; border-radius:6px; font-size:8px; font-weight:700; color:var(--brand); display:flex; align-items:flex-end; justify-content:center; padding-bottom:3px; background:#fff; }
.ld-typed { font-family:monospace; font-size:10.5px; line-height:1.5; color:var(--muted); background:#fff; border:1px solid var(--line); border-radius:8px; padding:8px 10px; text-align:left; }
.ld-vsbadge { display:flex; align-items:center; gap:8px; }
.ld-vsbadge span { width:38px; height:38px; border-radius:50%; background:#fff; border:2px solid var(--line); display:grid; place-items:center; font-weight:800; color:var(--ink); }
.ld-vsbadge b { font-family:'Outfit',sans-serif; font-size:22px; color:var(--brand); }

/* product picker cards */
[data-testid="stVerticalBlockBorderWrapper"]:has(.ld-pcard) { transition:transform .18s ease, box-shadow .18s ease; }
[data-testid="stVerticalBlockBorderWrapper"]:has(.ld-pcard):hover { transform:translateY(-3px); box-shadow:0 10px 24px rgba(28,25,23,.08); }
.ld-pcard { text-align:center; position:relative; }
.ld-pcard .img { height:112px; display:flex; align-items:center; justify-content:center; background:#fff; border-radius:10px; }
.ld-pcard img { transition:transform .25s ease; }
[data-testid="stVerticalBlockBorderWrapper"]:hover .ld-pcard img { transform:scale(1.07); }
.ld-pcard img { max-height:108px; max-width:100%; object-fit:contain; }
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
.ld-cmp .img { height:130px; display:flex; align-items:center; justify-content:center; }
.ld-cmp .img img { max-height:120px; max-width:90%; object-fit:contain; }
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
.ld-top .img { background:#fff; border:1px solid var(--line); border-radius:14px; height:180px; display:flex; align-items:center; justify-content:center; }
.ld-top .img img { max-height:calc(100% - 12px); max-width:calc(100% - 12px); object-fit:contain; }
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
.ld-cube { width:34px; height:34px; border-radius:8px; background:#fffbeb; border:2px solid #f59e0b;
  box-shadow:inset -5px -5px 0 #fde68a, 0 2px 0 #fcd34d; position:relative; overflow:hidden; animation:ld-pop .4s cubic-bezier(.3,1.5,.6,1) both; }
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

.ld-honest { font-size:15.5px; line-height:1.6; color:var(--ink); background:var(--brand-bg); border:1px dashed #fdba74; border-radius:14px; padding:16px 18px; }
.ld-footer { text-align:center; color:var(--faint); font-size:13.5px; margin-top:36px; padding-top:18px; border-top:1px solid var(--line); }
.ld-footer a { color:var(--brand); text-decoration:none; font-weight:600; }
.ld-empty { background:#fff; border:1px dashed var(--line); border-radius:16px; padding:22px; color:var(--muted); text-align:center; }

@media (max-width: 720px) {
  .ld-hero { padding:24px 18px 20px; } .ld-hero h1 { font-size:31px; }
  .ld-steps { flex-direction:column; } .ld-arrow { transform:rotate(90deg); text-align:center; }
  .ld-ab-grid { grid-template-columns:1fr; } .ld-pts { grid-template-columns:1fr; }
  .ld-intro { grid-template-columns:1fr; } .ld-intro .art { height:80px; }
  .ld-vs { grid-template-columns:1fr; } .ld-vs .mid { text-align:center; }
  .ld-stats, .ld-lights { grid-template-columns:repeat(2,1fr); }
  .ld-top { grid-template-columns:1fr; } .ld-top .img { height:150px; }
  .ld-name { font-size:24px; } .ld-grid2 { grid-template-columns:1fr; }
  .ld-claim { grid-template-columns:1fr; } .ld-claim .says { border-right:none; border-bottom:1px solid var(--line); }
}
</style>
"""


def esc(s) -> str:
    return html.escape("" if s is None else str(s)).replace("$", "&#36;")


def fmt(v, digits: int = 1) -> str:
    if v is None:
        return "—"
    return f"{v:.{digits}f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v)


def _tidy(s: str) -> str:
    s = re.sub(r"\s+", " ", (s or "").strip())
    return s.title() if s and (s.islower() or s.isupper()) else s


def display_name(brand: str | None, name: str | None) -> tuple[str, str]:
    """(brand, product name) with crowd-database noise removed: duplicate brand, pack size, ALL CAPS, lowercase."""
    b = _tidy((brand or "").split(",")[0])
    n = _tidy(re.sub(r"\s*\d+(\.\d+)?\s*(g|gm|kg|ml|l|ltr)\.?$", "", name or "", flags=re.I))
    if not n:
        return "", b or "Unnamed product"
    if b and n.lower().startswith(b.lower() + " "):
        n = n[len(b):].strip()
    return b, n


def full_name(brand: str | None, name: str | None) -> str:
    b, n = display_name(brand, name)
    return n if not b or b.lower() in n.lower() else f"{b} {n}"


# ---------------------------------------------------------------------------------------------
# hero and picker
# ---------------------------------------------------------------------------------------------

def hero() -> str:
    return (
        '<div class="ld-hero"><span class="ld-badge">🇮🇳 Indian Label Decoder</span>'
        '<h1>Healthy on the front.<br><em>Sugar</em> on the back.</h1>'
        '<p class="sub">Indian food labels are legally correct and practically useless. This app reads any pack and tells you:</p>'
        '<ul class="ld-pts">'
        '<li><i>🥄</i><span><b>Sugar in spoons</b>, not grams</span></li>'
        '<li><i>🎭</i><span><b>Every secret name</b> sugar hides under</span></li>'
        '<li><i>⚖️</i><span><b>“High protein”: true or not?</b> Checked against the law</span></li>'
        '<li><i>🎩</i><span><b>The trick</b> on the pack, and the rule behind it</span></li>'
        '</ul>'
        '<div class="ld-steps" id="how">'
        '<div class="ld-step"><div class="ic">📦</div><b>1. Pick a pack</b><span>tap, barcode or photo</span></div>'
        '<div class="ld-arrow">→</div>'
        '<div class="ld-step"><div class="ic">🔍</div><b>2. We read it</b><span>numbers, ingredients, claims</span></div>'
        '<div class="ld-arrow">→</div>'
        '<div class="ld-step"><div class="ic">✅</div><b>3. You get the truth</b><span>spoons, colours, plain words</span></div>'
        '</div>'
        '<div class="ld-stats">'
        '<div class="ld-stat"><b>100</b><span>Indian packs checked</span></div>'
        '<div class="ld-stat"><b>1 in 5</b><span>hide sugar under many names</span></div>'
        '<div class="ld-stat"><b>60+</b><span>secret names for sugar</span></div>'
        '<div class="ld-stat"><b>87%</b><span>accurate when reading photos</span></div>'
        '</div></div>'
    )


def about() -> str:
    """The whole project on one screen: problem, product, method, evidence, stack, author."""
    tiles = [
        ("🎯", "The problem", [
            "“No added sugar”, but sweetened with fruit syrup",
            "“High protein” per 100 g; you eat 25 g",
            "Sugar split into 3 names so none is #1",
            "<b>All legal. All misleading.</b>"]),
        ("📱", "What it does", [
            "In: photo, barcode or pasted text",
            "Out: sugar per serve, in spoons",
            "Every hidden name for sugar",
            "Each claim checked against the law",
            "Traffic lights + daily sugar budget"]),
        ("⚙️", "How it works", [
            "AI only <b>reads</b> the pack",
            "Verdicts come from <b>Python rules</b>, not AI",
            "60+ sugar names · FSSAI limits · 26 tricks",
            "Same pack = same answer, always",
            "23 unit tests"]),
        ("📊", "The evidence", [
            "100 Indian packs tested",
            "21 of 100 hide sugar under 2+ names",
            "Photo reading: <b>87% accurate</b>",
            "96% on clean packs; errors listed by field"]),
        ("🧰", "Built with", [
            "Python + Streamlit",
            "Claude / Gemini vision",
            "Open Food Facts API",
            "pytest, Pillow"]),
        ("👤", "Why I built it", [
            "PM portfolio project by Om Rana",
            "A real consumer problem",
            "Domain rules turned into code",
            "Measured, not just a demo"]),
    ]
    body = "".join(f'<div class="ld-ab"><div class="ic">{i}</div><b>{esc(t)}</b><ul>'
                   + "".join(f"<li>{p}</li>" for p in pts) + "</ul></div>" for i, t, pts in tiles)
    return (f'<div class="ld-card ld-about"><div class="ld-h2">The whole project in 30 seconds</div>'
            f'<div class="ld-h2-sub">Six boxes. Read top to bottom.</div><div class="ld-ab-grid">{body}</div></div>')


INTROS = {
    "suspects": ("The usual suspects",
                 "Eight packs everyone buys. Tap one. Prepare to be mildly betrayed.",
                 "Start with Cadbury Shots. It is the worst of the lot.",
                 '<div class="ld-art"><span>🍫</span><span>🥛</span><span>🧃</span><span>🍪</span></div>'),
    "barcode": ("Those 13 digits know everything",
                "The number under the black bars is the pack's ID. Type it, we fetch the label.",
                "Indian packs start with 890. Try 8901063139329 (Britannia Bourbon), or whatever is in your kitchen.",
                '<div class="ld-barcode"><div class="bars"></div><div class="num">8 901063 139329</div></div>'),
    "photo": ("Show us the pack",
              "Front, ingredients, nutrition table. Three photos, one truth.",
              "Flat and bright works best. Crumpled packs and glare are our weak spot: 66% accuracy there, 96% on clean shots.",
              '<div class="ld-frames"><div>Front</div><div>Ingredients</div><div>Nutrition</div></div>'),
    "paste": ("No camera? Type it",
              "Copy what the pack says, as messy as you like. We sort it out.",
              "Claims, the ingredient list, the nutrition table and the serve size. Even one of these is a start.",
              '<div class="ld-typed">No added sugar. High protein.<br>Ingredients: Oats (40%), Dates…<br>Per 100 g: Sugars 22 g…</div>'),
    "faceoff": ("Face-off",
                "Two packs enter. One has less sugar. Settle the kitchen argument.",
                "Try Horlicks vs White Oats, or Mishti Doi vs Classic Dahi.",
                '<div class="ld-vsbadge"><span>A</span><b>VS</b><span>B</span></div>'),
    "lineup": ("The full lineup",
               "All 100 packs we tested, A to Z. Find yours.",
               "Spoiler: Horlicks is 46% sugar. Parle-G is a quarter sugar. Maggi is a third of your day's salt.",
               '<div class="ld-art"><span>📚</span></div>'),
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
                 selected: bool = False, ribbon: str | None = None) -> str:
    n = full_name(brand, name)
    pic = f'<img src="{esc(img)}" alt="">' if img else '<span style="font-size:40px">📦</span>'
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
    return f'<div class="ld-pcard{" on" if selected else ""}">{rib}<div class="img">{pic}</div><div class="nm">{esc(n)}</div>{chip}</div>'


def navbar(github: str) -> str:
    return (f'<div class="ld-nav"><div class="logo"><i>🔍</i>Label Decoder</div>'
            f'<div class="links"><a href="#how">How it works</a><a href="{esc(github)}" target="_blank">GitHub</a>'
            f'<a class="cta" href="https://om-rana-portfolio.netlify.app" target="_blank">Made by Om Rana</a></div></div>')


def no_key_card() -> str:
    return ('<div class="ld-empty"><b>Photo reading is off on this copy</b> (it needs an AI key).<br>'
            'Pick one of <b>the usual suspects</b> or <b>scan a barcode</b>. Same results, no key needed.</div>')


def footer(github: str) -> str:
    return (f'<div class="ld-footer">Made by <b>Om Rana</b> · <a href="{esc(github)}" target="_blank">Code on GitHub</a><br>'
            'AI only reads the pack. The verdicts come from written rules (India\'s FSSAI food law + WHO sugar advice), '
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
    high_flags = [f for f in result["flags"] if f["severity"] == "high"]
    reds = [k for k, (_, lvl) in lights.items() if lvl == "red"]
    if high_flags or lights["sugar"][1] == "red" or len(reds) >= 2:
        return "red", "Careful!"
    if reds or result["flags"] or lights["sugar"][1] == "amber":
        return "amber", "Okay, sometimes"
    if all(lvl == "grey" for _, lvl in lights.values()):
        return "amber", "Not enough info"
    return "green", "Good to go"


def _reasons(result: dict, lights: dict, unit: str) -> tuple[str, list[str]]:
    s = result["sugar"]
    rank = result["consolidated_sugar"]
    names = {"sugar": "sugar", "fat": "fat", "satfat": "saturated fat", "salt": "salt"}
    out: list[str] = []
    headline = ""
    pct = s["total_sugars_per_100"]
    if pct is not None and lights["sugar"][1] != "green":
        pct = float(pct)
        tsp = s["teaspoons_total_per_serve"]
        if unit == "g":
            what = ("Almost three-quarters of this pack is sugar." if pct >= 70 else
                    "About half of this pack is sugar." if pct >= 45 else
                    "A third of this pack is sugar." if pct >= 30 else
                    "A fifth of this pack is sugar." if pct >= 18 else
                    f"{fmt(pct)} g of sugar in every 100 g.")
            headline = what + (f" One serve = {tsp:.1f} spoons." if tsp else "")
        else:
            headline = (f"One {fmt(s['serving_g'])} ml serve = {tsp:.1f} spoons of sugar." if tsp
                        else f"{fmt(pct)} g of sugar in every 100 ml.")
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


def top_card(label: dict, result: dict, img: str | None, lights: dict) -> str:
    p = result["product"]
    unit = "ml" if p["is_liquid"] else "g"
    brand, name = display_name(p.get("brand"), p.get("name"))
    color, word = verdict(result, lights)
    icon = {"red": "🔴", "amber": "🟡", "green": "🟢"}[color]
    headline, reasons = _reasons(result, lights, unit)
    pic = f'<img src="{esc(img)}" alt="">' if img else '<span class="ph">📦</span>'
    li = "".join(f"<li>{esc(r)}</li>" for r in reasons)
    serve = result["serving"]
    meta = f"One serve = {fmt(serve['g'])} {unit} ({esc(serve['source'])})" if serve["g"] else "The pack gives no serve size"
    if label.get("barcode"):
        meta += f" · Barcode {esc(label['barcode'])}"
    plain = {"red": "This is a treat, not food. Once in a while is fine.",
             "amber": "Okay now and then. Not every day.",
             "green": "Nothing sneaky here. Eat normally."}[color]
    return (f'<div class="ld-card"><div class="ld-top"><div class="img">{pic}</div><div>'
            f'<div class="ld-brand">{esc(brand)}</div><div class="ld-name">{esc(name)}</div>'
            f'<span class="ld-verdict {color}">{icon} {word}</span>'
            f'<div class="ld-headline">{esc(headline)}</div>'
            f'{"<ul class=ld-reasons>" + li + "</ul>" if li else ""}'
            f'<div class="ld-mean"><b>In plain words:</b> {plain}</div>'
            f'<div class="ld-meta">{meta}</div></div></div></div>')


def sugar_cards(result: dict) -> str:
    s = result["sugar"]
    unit = "ml" if result["product"]["is_liquid"] else "g"
    tsp = s["teaspoons_total_per_serve"]
    if tsp is None:
        left = ('<div class="ld-card"><div class="ld-h2">🥄 How many spoons of sugar?</div>'
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
        left = (f'<div class="ld-card"><div class="ld-h2">🥄 Spoons of sugar in one serve</div>'
                f'<div class="ld-h2-sub">One serve = {fmt(s["serving_g"])} {unit}. Each cube = 1 teaspoon.</div>'
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
        right = ('<div class="ld-card"><div class="ld-h2">📅 Your sugar budget for today</div>'
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
        right = (f'<div class="ld-card"><div class="ld-h2">📅 Your sugar budget for today</div>'
                 f'<div class="ld-h2-sub">Doctors say: max 6 spoons of added sugar a day. The dashed cubes are your day.</div>'
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
        line = f"Sweeter than <b>{below} of {n}</b> packs. Only {n - below - 1} are sweeter than this."
    elif below <= n * 0.2:
        line = f"One of the <b>least sugary</b> packs. {n - below - 1} of {n} have more sugar."
    else:
        line = f"Middle of the pack: sweeter than <b>{below} of {n}</b>."
    unit = "ml" if result["product"]["is_liquid"] else "g"
    return (f'<div class="ld-card"><div class="ld-h2">🏆 Versus {n} Indian packs</div>'
            f'<div class="ld-h2-sub">One bar = one pack. Tall = more sugar. Orange = this one.</div>'
            f'<div class="ld-dist">{bars}</div>'
            f'<div class="ld-dist-axis"><span>◀ least sugar ({fmt(vals[0])} g per 100 {unit})</span><span>most sugar ({fmt(vals[-1])} g) ▶</span></div>'
            f'<div class="ld-mean">{line}</div></div>')


def order_card(label: dict, result: dict) -> str:
    """The ingredient list as numbered chips: sugar lines lit up, combined-rank callout when split."""
    items = [i for i in (label.get("ingredients") or []) if not i.get("nested")]
    if len(items) < 3:
        return ""
    sugar_lines = {h["ingredient_line"].strip().lower() for h in result["sugar_lines"] if h["tier"] == "added"}
    chips = []
    for n, it in enumerate(items[:14], 1):
        nm = _tidy(it.get("name") or "")
        nm = nm[:30].rstrip() + "…" if len(nm) > 32 else nm
        cls = "sug" if (it.get("name") or "").strip().lower() in sugar_lines else ""
        pct = f' · {fmt(float(it["percent"]))}%' if it.get("percent") is not None else ""
        chips.append(f'<span class="{cls}"><b>{n}</b>{esc(nm)}{esc(pct)}</span>')
    more = f'<span><b>…</b>{len(items) - 14} more</span>' if len(items) > 14 else ""
    rank = result["consolidated_sugar"]
    call = ""
    if rank.get("n_added_sugar_lines", 0) >= 2 and rank.get("combined_rank_estimate"):
        call = (f'<div class="ld-callout">Join the {rank["n_added_sugar_lines"]} yellow pieces and sugar jumps to '
                f'<b>#{rank["combined_rank_estimate"]}</b>. Legal, but sneaky.</div>')
    return (f'<div class="ld-card"><div class="ld-h2">📋 What\'s inside, biggest first</div>'
            f'<div class="ld-h2-sub">The law: heaviest ingredient first. #1 is most of the pack. Yellow = sugar.</div>'
            f'<div class="ld-order">{"".join(chips)}{more}</div>{call}</div>')


def compare_card(label: dict, result: dict, img: str | None, lights: dict, winner: bool) -> str:
    p = result["product"]
    name = full_name(p.get("brand"), p.get("name"))
    color, word = verdict(result, lights)
    icon = {"red": "🔴", "amber": "🟡", "green": "🟢"}[color]
    s = result["sugar"]
    tsp = s["teaspoons_total_per_serve"]
    unit = "ml" if p["is_liquid"] else "g"
    pic = f'<img src="{esc(img)}" alt="">' if img else '<span style="font-size:48px">📦</span>'
    labels = {"sugar": "Sugar", "fat": "Fat", "satfat": "Sat fat", "salt": "Salt"}
    mini = "".join(f'<div class="{lvl}"><b>{fmt(float(v)) if v is not None else "—"}</b>{labels[k]}</div>'
                   for k, (v, lvl) in lights.items())
    return (f'<div class="ld-cmp"><div class="img">{pic}</div><div class="nm">{esc(name)}</div>'
            f'<span class="ld-verdict {color}">{icon} {word}</span>'
            f'<div class="big">{f"{tsp:.1f}" if tsp is not None else "—"} <small>tsp sugar per {fmt(s["serving_g"])} {unit}</small></div>'
            f'<div class="mini">{mini}</div>'
            f'{"<div class=win>🏅 Less sugar</div>" if winner else "<div class=win>&nbsp;</div>"}</div>')


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
    im = Image.new("RGB", (W, H), "#faf7f2")
    d = ImageDraw.Draw(im)
    color, word = verdict(result, lights)
    hexes = {"red": "#dc2626", "amber": "#d97706", "green": "#16a34a"}
    d.rectangle([0, 0, W, 18], fill=hexes[color])
    p = result["product"]
    name = full_name(p.get("brand"), p.get("name"))
    d.text((70, 70), "INDIAN LABEL DECODER", font=font(26), fill="#ea580c")
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
            d.rounded_rectangle([x, y, x + 62, y + 62], radius=12, fill="#fde68a", outline="#f59e0b", width=4); x += 76
        if part >= 0.1 and full < 12:
            d.rounded_rectangle([x, y, x + 62, y + 62], radius=12, fill="#fffbeb", outline="#f59e0b", width=4)
            d.rectangle([x + 4 + 54 * part, y + 4, x + 58, y + 58], fill="#fffbeb")
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
    word = {"red": "🔴 HIGH", "amber": "🟡 MEDIUM", "green": "🟢 LOW", "grey": "NOT ON PACK"}
    tiles = "".join(
        f'<div class="ld-light {lvl}"><div class="k">{labels[k]}</div>'
        f'<div class="v">{fmt(float(v)) + " g" if v is not None else "—"}</div><div class="l">{word[lvl]}</div></div>'
        for k, (v, lvl) in lights.items())
    reds = [labels[k].lower() for k, (_, lvl) in lights.items() if lvl == "red"]
    meaning = ("Red = too much " + " and ".join(reds) + " in every bite."
               if reds else "No red. Nothing in the danger zone." if any(l != "grey" for _, l in lights.values())
               else "The pack does not print these numbers.")
    return (f'<div class="ld-card"><div class="ld-h2">🚦 Traffic lights (per {unit})</div>'
            f'<div class="ld-h2-sub">🟢 Go · 🟡 Sometimes · 🔴 Careful. Same cut-offs the UK prints on pack fronts.</div>'
            f'<div class="ld-lights">{tiles}</div><div class="ld-mean">{meaning}</div></div>')


def flags_card(flags: list[dict]) -> str:
    if not flags:
        return ('<div class="ld-card"><div class="ld-h2">🎩 Tricks on this pack</div>'
                '<div class="ld-h2-sub">No tricks found. The numbers above are the whole story.</div></div>')
    sev = {"high": "Big trick", "medium": "Watch out", "low": "Small thing"}
    items = "".join(
        f'<div class="ld-flag {f["severity"]}"><div class="t"><span class="ld-sev {f["severity"]}">{sev[f["severity"]]}</span>'
        f'{esc(f["title"])}</div><div class="d">{esc(SIMPLE.get(f["code"], f["detail"]))}</div>'
        f'<div class="r">Small print: {esc(f["detail"])}<br>The rule: {esc(f["rule_ref"])}</div></div>'
        for f in flags)
    return (f'<div class="ld-card"><div class="ld-h2">🎩 Tricks on this pack</div>'
            f'<div class="ld-h2-sub">{len(flags)} thing{"s" if len(flags) != 1 else ""} that {"are" if len(flags) != 1 else "is"} legal, but can fool you</div>{items}</div>')


CLAIM_VERDICT = {
    "holds": ("green", "✅ True"),
    "fails": ("red", "❌ Not true"),
    "legal but misleading": ("amber", "⚠️ True on paper, not on your plate"),
    "unverifiable": ("grey", "🤷 Can't check: the pack skips that number"),
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
    return (f'<div class="ld-card"><div class="ld-h2">🗣️ Pack says vs. truth</div>'
            f'<div class="ld-h2-sub">Every claim on the front, checked against the law</div>{"".join(rows)}{vs}</div>')


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
    return (f'<div class="ld-card"><div class="ld-h2">🎭 Sugar\'s disguises</div><div class="ld-h2-sub">{sub}</div>'
            f'{"<div class=ld-names>" + "".join(chips) + "</div>" if chips else ""}{body}{why}</div>')


def honest_card(result: dict) -> str:
    if not result["honest_label"]:
        return ""
    return (f'<div class="ld-card"><div class="ld-h2">✅ The honest label</div>'
            f'<div class="ld-h2-sub">If the pack had nothing to sell you</div>'
            f'<div class="ld-honest">{esc(result["honest_label"])}</div></div>')
