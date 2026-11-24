"""
Indian Label Decoder - Streamlit app.

    streamlit run app.py

Ways in: a popular pack, a barcode (Open Food Facts), photo(s) of the pack, or pasted label
text. Photo and text need a model key (ANTHROPIC_API_KEY or GEMINI_API_KEY); everything else
works offline because the rules layer is pure Python. The look and the page motion are the
website's own (src/ui.py shared, src/app_ui.py for Streamlit's widgets), so this app and the
static site read the same.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# A hosted copy (Streamlit Community Cloud) keeps the model key under "Secrets". src/llm.py reads the
# environment, so copy it across once. On a laptop with no secrets file this does nothing.
for _k in ("GEMINI_API_KEY", "ANTHROPIC_API_KEY"):
    if not os.environ.get(_k):
        try:
            if _k in st.secrets:
                os.environ[_k] = str(st.secrets[_k])
        except Exception:
            pass

from src import app_ui, ui  # noqa: E402
from src.llm import provider  # noqa: E402
from src.off_api import drop_implausible, fetch_product, to_label  # noqa: E402
from src.replays import replay_cards  # noqa: E402
from src.rules.decoder import decode_label  # noqa: E402

GITHUB = "https://github.com/amustprocoder/Label-Decoder-"
SAMPLES = ROOT / "eval" / "data" / "testset.jsonl"
# Picked to show each kind of trick (and to have a clean front photo): sugar under many names, a "high protein"
# claim, a drink that blows the daily limit, salt and saturated fat.
FEATURED = ["7622201150303", "8901063093287", "8906080603938", "8901719125478",
            "8904004400212", "8901058006292", "8906059638329", "6294017124031"]

# Three real packs with their photos in the repo, so anyone can watch a live read without a pack in hand.
SAMPLE_DIR = ROOT / "samples"
SAMPLE_PACKS = [("8901719125478", "Parle-G Gold"), ("8901058006292", "Maggi 2-Minute Noodles"),
                ("7622201150303", "Cadbury Shots")]
MAX_AI_READS = 10     # per visit: the hosted copy runs on a free-tier key

st.set_page_config(page_title="Label Decoder: is this pack healthy?", page_icon="🔍", layout="wide")
st.markdown(ui.CSS + ui.SITE_CSS + app_ui.APP_CSS, unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def load_samples() -> dict[str, dict]:
    """barcode -> {"label", "img" (front photo URL), "image_urls"} for the 100-product test set."""
    if not SAMPLES.exists():
        return {}
    out = {}
    for line in SAMPLES.open(encoding="utf-8"):
        r = json.loads(line)
        urls = r.get("image_urls") or {}
        out[r["barcode"]] = {"label": r["label"], "img": urls.get("front"), "image_urls": urls}
    return out


@st.cache_data(show_spinner=False)
def all_sugar_values() -> list[float]:
    return [float(v) for s in load_samples().values()
            if (v := (s["label"].get("per_100") or {}).get("total_sugars_g")) is not None]


@st.cache_data(show_spinner=False)
def live_show() -> list[dict]:
    """The packs the "Decoding now" strip cycles through: the featured eight, same verdict logic as their cards."""
    samples, out = load_samples(), []
    for code in FEATURED:
        if code in samples:
            item = app_ui.live_item(code, samples[code]["label"], decode_label(samples[code]["label"]), samples[code]["img"])
            if item:
                out.append(item)
    return out


@st.cache_data(show_spinner=False)
def replay_html() -> list[tuple]:
    return replay_cards(load_samples())


@st.cache_data(show_spinner=False)
def sample_thumb(path: str) -> str | None:
    return thumb(Path(path).read_bytes())


def render(label: dict, result: dict, img: str | None = None, key: str = "x") -> None:
    per100 = label.get("per_100") or {}
    liquid = result["product"]["is_liquid"]
    lights = ui._lights(per100, liquid)
    # the verdict, three facts and the spoons come first; the rest follows in the same scroll
    st.html(ui.top_card(label, result, img, lights) + ui.health_card(result) + ui.three_things(result, lights))
    st.html(ui.sugar_cards(result))
    st.html(ui.rank_card(result, all_sugar_values()) + ui.lights_card(lights, liquid))
    # claim verdicts already have their own card; keep the flag list for everything else
    flags = [f for f in result["flags"] if not (result["claims"] and f["code"] in ("PER100_VS_SERVE", "CLAIM_FAILS"))]
    st.html(ui.claims_card(result["claims"], result["serving"]["g"], "ml" if liquid else "g") + ui.flags_card(flags))
    st.html(ui.order_card(label, result) + ui.sugar_names_card(label, result) + ui.honest_card(result))
    c1, c2 = st.columns([1, 3], vertical_alignment="center")
    c1.download_button("Download share card (PNG)", data=ui.share_image(label, result, lights),
                       file_name=f"label-decoder-{(label.get('barcode') or 'pack')}.png", mime="image/png",
                       key=f"dl_{key}_{label.get('barcode')}", use_container_width=True)
    c2.caption("Get this as a picture. Send it on WhatsApp or post it.")
    with st.expander("Nerd corner: the raw numbers"):
        st.caption("First the label as the rules saw it, then everything the decoder worked out.")
        st.json({k: v for k, v in label.items() if k != "images"}, expanded=False)
        st.json(result, expanded=False)


def sample_photos(code: str) -> list[Path]:
    return [p for kind in ("front", "ingredients", "nutrition") if (p := SAMPLE_DIR / f"{code}_{kind}.jpg").exists()]


def thumb(raw: bytes) -> str | None:
    """A small data-URI copy of a photo, so the result card can show the pack that was read."""
    try:
        import base64
        import io

        from PIL import Image
        im = Image.open(io.BytesIO(raw)).convert("RGB")
        im.thumbnail((420, 420))
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=82)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception:
        return None


def run_ai(slot: str, fn, arg, spinner: str, what: str) -> None:
    """One live model read. The answer is kept in the session, so a rerun (the download button, a tab click)
    does not throw it away. `arg` is a list of photo bytes or a string of pasted text."""
    used = st.session_state.get("ai_reads", 0)
    if used >= MAX_AI_READS:
        st.session_state[slot] = {"error": f"This demo allows {MAX_AI_READS} AI reads per visit. "
                                           "The barcode tab and the 100 packs have no limit."}
        return
    st.session_state["ai_reads"] = used + 1
    t0 = time.time()
    with st.spinner(spinner):
        try:
            label = fn(arg)
            shots = arg if isinstance(arg, list) else []
            st.session_state[slot] = {"label": label, "secs": time.time() - t0,
                                      "thumbs": [t for b in shots if (t := thumb(b))]}
        except Exception as e:  # surface the provider error, do not guess
            st.session_state[slot] = {"error": f"Could not read the {what}: {e}"}


def show_ai(slot: str, key: str) -> None:
    out = st.session_state.get(slot)
    if not out:
        return
    if out.get("error"):
        st.error(out["error"])
        return
    label = out["label"]
    thumbs = out.get("thumbs") or []
    # step 1, the transcription on its own, before any rule runs: this is all the model contributes
    st.html(app_ui.live_read_card(label, thumbs, out.get("secs")))
    render(label, decode_label(label), thumbs[0] if thumbs else None, key=key)


samples = load_samples()
st.html(ui.navbar(GITHUB, lang_toggle=True))
st.html(app_ui.scribbles() + ui.hero(cta=True))
st.html(app_ui.live_strip())
st.html(ui.about())

tab_pop, tab_dash, tab_cmp, tab_ai, tab_photo, tab_text, tab_barcode, tab_all = st.tabs(
    ["The usual suspects", "The big picture", "Face-off", "Watch the AI read", "Snap the pack", "Paste the fine print",
     "Scan a barcode", "The full lineup"])

with tab_pop:
    st.html(ui.intro("suspects"))
    feat = [b for b in FEATURED if b in samples]
    if not feat:
        st.html('<div class="ld-empty">Run <code>python eval/build_testset.py</code> once to load the sample packs.</div>')
    else:
        pick = st.session_state.setdefault("pick", feat[0])
        decoded = {c: decode_label(samples[c]["label"]) for c in feat}
        sugar = {c: (samples[c]["label"].get("per_100") or {}).get("total_sugars_g") for c in feat}
        ribbons = {}
        with_sugar = [c for c in feat if sugar[c] is not None]
        if with_sugar:
            ribbons[max(with_sugar, key=lambda c: sugar[c])] = "MOST SUGAR"
            ribbons.setdefault(min(with_sugar, key=lambda c: sugar[c]), "LEAST SUGAR")
        ribbons.setdefault(max(feat, key=lambda c: decoded[c]["severity_score"]), "BIGGEST TRICK")
        for row in range(0, len(feat), 4):
            cols = st.columns(4)
            for col, code in zip(cols, feat[row:row + 4]):
                s = samples[code]
                lab = s["label"]
                with col.container(border=True):
                    st.html(ui.product_card(lab.get("brand"), lab.get("product_name"), s["img"], sugar[code],
                                            decoded[code]["product"]["is_liquid"],
                                            selected=(code == pick), ribbon=ribbons.get(code), code=code))
                    if st.button("Showing ↓" if code == pick else "Check this pack",
                                 key=f"pick_{code}", use_container_width=True,
                                 type="primary" if code == pick else "secondary"):
                        st.session_state.pick = code
                        st.rerun()
        s = samples[st.session_state.pick]
        render(s["label"], decode_label(s["label"]), s["img"], key="pop")

with tab_dash:
    st.html(ui.intro("bigpicture"))
    if samples:
        st.html(ui.dashboard([(s["label"], decode_label(s["label"])) for s in samples.values()]))

with tab_cmp:
    st.html(ui.intro("faceoff"))
    if not samples:
        st.html('<div class="ld-empty">Run <code>python eval/build_testset.py</code> once to load the 100 products.</div>')
    else:
        def _nm(c: str) -> str:
            return ui.full_name(samples[c]["label"].get("brand"), samples[c]["label"].get("product_name"))
        codes = sorted(samples, key=lambda c: _nm(c).lower())
        c1, c2 = st.columns(2)
        a = c1.selectbox("Pack A", codes, format_func=_nm, index=codes.index("8906059638329") if "8906059638329" in codes else 0)
        b = c2.selectbox("Pack B", codes, format_func=_nm, index=codes.index("8901648026167") if "8901648026167" in codes else 1)
        res = {}
        for code in (a, b):
            lab = samples[code]["label"]
            r = decode_label(lab)
            res[code] = (lab, r, ui._lights(lab.get("per_100") or {}, r["product"]["is_liquid"]))
        tsp = {c: res[c][1]["sugar"]["teaspoons_total_per_serve"] for c in (a, b)}
        win = None
        if tsp[a] is not None and tsp[b] is not None and tsp[a] != tsp[b]:
            win = a if tsp[a] < tsp[b] else b
        for col, code in ((c1, a), (c2, b)):
            lab, r, lights = res[code]
            cls = "" if not win else (" win" if code == win else " lose")   # the winner lifts, the other steps back
            col.html(ui.compare_card(lab, r, samples[code]["img"], lights, winner=(code == win))
                     .replace('<div class="ld-cmp">', f'<div class="ld-cmp{cls}">', 1))
        if win and tsp[a] and tsp[b]:
            lo, hi = sorted((tsp[a], tsp[b]))
            st.html(f'<div class="ld-card" style="text-align:center;font-size:17px">{ui.icon("medal")} <b>{ui.esc(_nm(win))}</b> wins: '
                    f'<b>{hi / lo:.1f}× less sugar</b> per serve.</div>' if lo > 0 else "")

with tab_ai:
    st.html(ui.intro("airead"))
    cards = replay_html()
    if cards:
        st.html(app_ui.replay_panel(cards), unsafe_allow_javascript=True)
    else:
        st.html('<div class="ld-empty">The recorded readings (eval/results) are not on this copy.</div>')
    st.html('<div class="ld-empty"><b>Want to try your own photo?</b><br>Open <b>Snap the pack</b>: the AI reads it live, '
            'the same way, and the rules decide.</div>')

with tab_photo:
    st.html(ui.intro("photo"))
    prov = provider()
    if prov is None:
        st.html(ui.no_key_card())
    else:
        from src.extract import extract_from_images
        files = st.file_uploader("Upload 1 to 4 photos of one pack: the front, the ingredients, the nutrition table",
                                 type=["jpg", "jpeg", "png", "webp"], accept_multiple_files=True)
        if files and st.button("Decode photos", type="primary"):
            run_ai("ai_photo", extract_from_images, [f.getvalue() for f in files[:4]], "Reading the label...", "photos")
        ready = [(c, n) for c, n in SAMPLE_PACKS if sample_photos(c)]
        if ready:
            st.html('<div class="ld-h2" style="margin-top:8px">No pack near you? Try one of ours.</div>'
                    '<div class="ld-h2-sub">The AI reads these photos now, live. Nothing is saved in advance.</div>')
            for col, (code, name) in zip(st.columns(len(ready)), ready):
                shots = sample_photos(code)
                with col.container(border=True):
                    st.html(app_ui.sample_card(name, sample_thumb(str(shots[0])), len(shots)))
                    if st.button(f"Read {name} live", key=f"smp_{code}", use_container_width=True):
                        run_ai("ai_photo", extract_from_images, [p.read_bytes() for p in shots],
                               f"The AI is reading {len(shots)} photos of {name}...", "photos")
        show_ai("ai_photo", "ph")

with tab_text:
    st.html(ui.intro("paste"))
    prov = provider()
    if prov is None:
        st.html(ui.no_key_card())
    else:
        txt = st.text_area("Paste what is written on the pack: claims, ingredients, nutrition table, serve size",
                           height=200, placeholder="No added sugar. High protein.\nIngredients: Oats (40%), Dates, ...\n"
                                                   "Nutrition per 100 g: Energy 420 kcal, Protein 12 g, Total sugars 22 g ...\n"
                                                   "Serving size 40 g")
        if txt and st.button("Decode text", type="primary"):
            from src.extract import extract_from_text
            run_ai("ai_text", extract_from_text, txt, "Reading the text...", "text")
        show_ai("ai_text", "tx")

with tab_barcode:
    st.html(ui.intro("barcode"))
    c1, c2 = st.columns([4, 1], vertical_alignment="bottom")
    code = c1.text_input("Type the 13 digits printed under the black bars (Indian packs start with 890)",
                         placeholder="e.g. 8901063139329  (Britannia Bourbon)")
    go = c2.button("Check it", type="primary", use_container_width=True)
    if code and go:
        with st.spinner("Fetching from Open Food Facts..."):
            prod = fetch_product(code.strip())
        if not prod:
            st.error("We do not know this barcode yet. Try snapping a photo of the pack instead.")
        else:
            label = to_label(prod)
            imgs = label.get("images") or {}
            dropped = drop_implausible(label)
            if dropped:
                st.info("Someone typed impossible numbers into the database. We ignored these: " + ", ".join(dropped))
            render(label, decode_label(label), imgs.get("front"), key="bc")
            pics = "".join(f'<figure><img src="{ui.esc(imgs[k])}" alt=""><figcaption>{k}</figcaption></figure>'
                           for k in ("front", "ingredients", "nutrition") if imgs.get(k))
            if pics:
                st.html(f'<div class="ld-card"><div class="ld-h2-sub">These numbers come from Open Food Facts, which anyone '
                        f'can edit. Check them against the photos.</div><div class="ld-photos">{pics}</div></div>')

with tab_all:
    st.html(ui.intro("lineup"))
    if not samples:
        st.html('<div class="ld-empty">Run <code>python eval/build_testset.py</code> once to load the 100 products.</div>')
    else:
        def _name(c: str) -> str:
            b, n = ui.display_name(samples[c]["label"].get("brand"), samples[c]["label"].get("product_name"))
            return f"{n} · {b}" if b else n
        codes = sorted(samples, key=lambda c: _name(c).lower())
        sel = st.selectbox("Pick any of the 100 packs we checked", codes, format_func=_name,
                           index=codes.index(FEATURED[0]) if FEATURED[0] in codes else 0)
        render(samples[sel]["label"], decode_label(samples[sel]["label"]), samples[sel]["img"], key="all")

st.html(ui.method())
st.html(ui.footer(GITHUB))
# the page script: motion, scroll reveal, the live strip and the Hindi switch. Last, so the page exists when it runs.
st.html(app_ui.app_js(live_show()), unsafe_allow_javascript=True)
