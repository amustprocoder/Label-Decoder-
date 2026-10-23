"""
Indian Label Decoder - Streamlit app.

    streamlit run app.py

Ways in: a popular pack, a barcode (Open Food Facts), photo(s) of the pack, or pasted label
text. Photo and text need a model key (ANTHROPIC_API_KEY or GEMINI_API_KEY); everything else
works offline because the rules layer is pure Python. Presentation lives in src/ui.py.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src import ui  # noqa: E402
from src.llm import provider  # noqa: E402
from src.off_api import drop_implausible, fetch_product, to_label  # noqa: E402
from src.rules.decoder import decode_label  # noqa: E402

GITHUB = "https://github.com/amustprocoder/Label-Decoder-"
SAMPLES = ROOT / "eval" / "data" / "testset.jsonl"
# Picked to show each kind of trick: health-drink sugar, sugar under many names, a "high protein"
# claim, a drink that blows the daily limit, salt and saturated fat.
FEATURED = ["7622201150303", "8901030807190", "8906080603938", "8901719125478",
            "8904004400212", "8901058006292", "8906059638329", "6294017124031"]

st.set_page_config(page_title="Indian Label Decoder", page_icon="🔍", layout="wide")
st.markdown(ui.CSS, unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def load_samples() -> dict[str, dict]:
    """barcode -> {"label": ..., "img": front photo URL} for the 100-product test set."""
    if not SAMPLES.exists():
        return {}
    out = {}
    for line in SAMPLES.open(encoding="utf-8"):
        r = json.loads(line)
        out[r["barcode"]] = {"label": r["label"], "img": (r.get("image_urls") or {}).get("front")}
    return out


@st.cache_data(show_spinner=False)
def all_sugar_values() -> list[float]:
    return [float(v) for s in load_samples().values()
            if (v := (s["label"].get("per_100") or {}).get("total_sugars_g")) is not None]


def render(label: dict, result: dict, img: str | None = None, key: str = "x") -> None:
    per100 = label.get("per_100") or {}
    liquid = result["product"]["is_liquid"]
    lights = ui._lights(per100, liquid)
    st.html(ui.top_card(label, result, img, lights))
    st.html(ui.sugar_cards(result))
    st.html(ui.rank_card(result, all_sugar_values()) + ui.lights_card(lights, liquid))
    # claim verdicts already have their own card; keep the flag list for everything else
    flags = [f for f in result["flags"] if not (result["claims"] and f["code"] in ("PER100_VS_SERVE", "CLAIM_FAILS"))]
    st.html(ui.claims_card(result["claims"], result["serving"]["g"], "ml" if liquid else "g") + ui.flags_card(flags))
    st.html(ui.order_card(label, result) + ui.sugar_names_card(label, result) + ui.honest_card(result))
    c1, c2 = st.columns([1, 3], vertical_alignment="center")
    c1.download_button("⬇ Share card (PNG)", data=ui.share_image(label, result, lights),
                       file_name=f"label-decoder-{(label.get('barcode') or 'pack')}.png", mime="image/png",
                       key=f"dl_{key}_{label.get('barcode')}", use_container_width=True)
    c2.caption("Get this as a picture. Send it on WhatsApp or post it.")
    with st.expander("🔬 Nerd corner: the raw numbers"):
        st.caption("First the label as the rules saw it, then everything the decoder worked out.")
        st.json({k: v for k, v in label.items() if k != "images"}, expanded=False)
        st.json(result, expanded=False)


st.html(ui.navbar(GITHUB))
st.html(ui.hero())
st.html(ui.about())
samples = load_samples()
st.html(ui.marquee([
    ("Horlicks", "is almost half sugar. 3.5 spoons in one scoop."),
    ("Cadbury Shots", "72% sugar, hidden under 2 names."),
    ("1 in 5 packs", "cut sugar into pieces so it never looks like #1."),
    ("Soya Chips", "say “rich in protein”. One serve = 7% of your day."),
    ("Paper Boat", "1 bottle = more sugar than a whole day should have."),
    ("Maggi", "1 pack = a third of a day's salt."),
]))

tab_pop, tab_barcode, tab_photo, tab_text, tab_cmp, tab_all = st.tabs(
    ["The usual suspects", "Scan a barcode", "Snap the pack", "Paste the fine print", "Face-off", "The full lineup"])

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
                                            selected=(code == pick), ribbon=ribbons.get(code)))
                    if st.button("Showing ↓" if code == pick else "Check this pack",
                                 key=f"pick_{code}", use_container_width=True,
                                 type="primary" if code == pick else "secondary"):
                        st.session_state.pick = code
                        st.rerun()
        s = samples[st.session_state.pick]
        render(s["label"], decode_label(s["label"]), s["img"], key="pop")

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
            st.caption("These numbers come from Open Food Facts, which anyone can edit. Check them against the photos below.")
            cols = st.columns(3)
            for col, kind in zip(cols, ("front", "ingredients", "nutrition")):
                if imgs.get(kind):
                    col.image(imgs[kind], caption=kind.capitalize(), use_container_width=True)

with tab_photo:
    st.html(ui.intro("photo"))
    prov = provider()
    if prov is None:
        st.html(ui.no_key_card())
    else:
        files = st.file_uploader("Upload 1 to 4 photos of one pack: the front, the ingredients, the nutrition table",
                                 type=["jpg", "jpeg", "png", "webp"], accept_multiple_files=True)
        if files and st.button("Decode photos", type="primary"):
            from src.extract import extract_from_images
            with st.spinner("Reading the label..."):
                try:
                    label = extract_from_images([f.getvalue() for f in files[:4]])
                except Exception as e:  # surface the provider error, do not guess
                    st.error(f"Could not read the photos: {e}")
                    label = None
            if label:
                if label.get("legibility") == "poor":
                    st.warning(f"Label hard to read, so some numbers may be off: {label.get('notes')}")
                render(label, decode_label(label), key="ph")

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
            with st.spinner("Reading the text..."):
                try:
                    label = extract_from_text(txt)
                except Exception as e:
                    st.error(f"Could not read the text: {e}")
                    label = None
            if label:
                render(label, decode_label(label), key="tx")

with tab_cmp:
    st.html(ui.intro("faceoff"))
    if not samples:
        st.html('<div class="ld-empty">Run <code>python eval/build_testset.py</code> once to load the 100 products.</div>')
    else:
        def _nm(c: str) -> str:
            return ui.full_name(samples[c]["label"].get("brand"), samples[c]["label"].get("product_name"))
        codes = sorted(samples, key=lambda c: _nm(c).lower())
        c1, c2 = st.columns(2)
        a = c1.selectbox("Pack A", codes, format_func=_nm, index=codes.index("8901030807190") if "8901030807190" in codes else 0)
        b = c2.selectbox("Pack B", codes, format_func=_nm, index=codes.index("8902710100150") if "8902710100150" in codes else 1)
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
            col.html(ui.compare_card(lab, r, samples[code]["img"], lights, winner=(code == win)))
        if win and tsp[a] and tsp[b]:
            lo, hi = sorted((tsp[a], tsp[b]))
            st.html(f'<div class="ld-card" style="text-align:center;font-size:17px">🏅 <b>{ui.esc(_nm(win))}</b> wins: '
                    f'<b>{hi / lo:.1f}× less sugar</b> per serve.</div>' if lo > 0 else "")

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

st.html(ui.footer(GITHUB))
