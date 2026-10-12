"""
Indian Label Decoder - Streamlit app.

    streamlit run app.py

Three ways in: photo(s) of the pack, pasted label text, or a barcode (Open Food Facts).
Photo and text need a model key (ANTHROPIC_API_KEY or GEMINI_API_KEY); barcode and the
built-in examples work offline because the rules layer is pure Python.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.llm import provider  # noqa: E402
from src.off_api import drop_implausible, fetch_product, to_label  # noqa: E402
from src.rules.decoder import decode_label  # noqa: E402

st.set_page_config(page_title="Indian Label Decoder", page_icon=":mag:", layout="wide")
st.title("Indian Label Decoder")
st.caption("Legally correct labels, practically useless. Paste the pack, get the sugar in teaspoons, "
           "the claim maths per serve, and the FSSAI rule each trick hides behind.")

SAMPLES = ROOT / "eval" / "data" / "testset.jsonl"


@st.cache_data(show_spinner=False)
def load_samples() -> list[dict]:
    if not SAMPLES.exists():
        return []
    rows = [json.loads(l) for l in SAMPLES.open(encoding="utf-8")]
    return [r["label"] for r in rows if r.get("label", {}).get("per_100", {}).get("total_sugars_g") is not None][:60]


def sev_icon(s: str) -> str:
    return {"high": "\U0001F534", "medium": "\U0001F7E0", "low": "\U0001F7E1"}[s]   # red / orange / yellow circle


def render(label: dict, result: dict) -> None:
    p = result["product"]
    unit = "ml" if p["is_liquid"] else "g"
    st.subheader(f"{p.get('brand') or ''} {p.get('name') or 'Unnamed product'}".strip())
    st.markdown(f"**{result['share_line']}**")

    s = result["sugar"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Sugar by weight", f"{s['total_sugars_per_100']:g}%" if s["total_sugars_per_100"] is not None else "n/a")
    c2.metric(f"Per {s['serving_g']:g} {unit} serve", f"{s['teaspoons_total_per_serve']:.1f} tsp" if s["teaspoons_total_per_serve"] is not None else "n/a",
              help=s["serving_source"])
    c3.metric("Added sugar / serve", f"{s['teaspoons_added_per_serve']:.1f} tsp" if s["teaspoons_added_per_serve"] is not None else "unknown",
              help=s["added_sugar_method"])
    c4.metric("Share of WHO 25 g/day", f"{s['pct_of_who_25g_per_serve']:.0f}%" if s["pct_of_who_25g_per_serve"] is not None else "n/a")

    if result["flags"]:
        st.markdown("### Where the pack misleads")
        for f in result["flags"]:
            with st.expander(f"{sev_icon(f['severity'])} {f['title']}", expanded=f["severity"] == "high"):
                st.write(f["detail"])
                st.caption(f"Rule: {f['rule_ref']}")
    else:
        st.success("No mislead patterns found on this label.")

    if result["claims"]:
        st.markdown("### Claim vs. maths")
        rows = []
        for c in result["claims"]:
            rows.append({"Claim on pack": c["claim_text"], "Read as": c["claim_type"], "Verdict": c["verdict"],
                         f"Actual / 100 {unit}": c["actual_per_100"], "Threshold": c["threshold"],
                         "Per serve": None if c["per_serving_value"] is None else round(c["per_serving_value"], 1),
                         "% RDA per serve": None if c["per_serving_pct_rda"] is None else round(c["per_serving_pct_rda"]),
                         "Legal test": c["legal_test"]})
        st.dataframe(rows, use_container_width=True, hide_index=True)

    cs = result["consolidated_sugar"]
    if result["sugar_lines"]:
        st.markdown("### Sugar, under all its names")
        st.write(cs["note"].capitalize() + ".")
        st.dataframe([{"#": h["position"], "On the label": h["ingredient_line"][:80], "Actually": h["canonical"], "Tier": h["tier"],
                       "%": h["percent"]} for h in result["sugar_lines"]], use_container_width=True, hide_index=True)

    with st.expander("Honest label (plain text to copy)"):
        st.write(result["honest_label"])
    with st.expander("Raw decoded JSON"):
        st.json(result)
    with st.expander("Structured label the decoder saw"):
        st.json({k: v for k, v in label.items() if k != "images"})


tab_photo, tab_text, tab_barcode, tab_examples = st.tabs(["Photo", "Paste text", "Barcode", "Examples"])

with tab_photo:
    prov = provider()
    if prov is None:
        st.warning("No model key found. Set ANTHROPIC_API_KEY or GEMINI_API_KEY to use photo and text input. "
                   "Barcode and Examples work without one.")
    files = st.file_uploader("Front, ingredients and nutrition panel (1 to 4 photos of the same pack)",
                             type=["jpg", "jpeg", "png", "webp"], accept_multiple_files=True)
    if files and st.button("Decode photos", disabled=prov is None):
        from src.extract import extract_from_images
        with st.spinner(f"Reading the label with {prov}..."):
            try:
                label = extract_from_images([f.getvalue() for f in files[:4]])
            except Exception as e:  # surface the provider error, do not guess
                st.error(f"Extraction failed: {e}")
                label = None
        if label:
            if label.get("legibility") == "poor":
                st.warning(f"Label hard to read: {label.get('notes')}")
            render(label, decode_label(label))

with tab_text:
    prov = provider()
    txt = st.text_area("Paste everything on the pack: claims, ingredient list, nutrition table, serving size",
                       height=220, placeholder="No added sugar. High protein.\nIngredients: Oats (40%), Dates, ...\n"
                                               "Nutrition per 100 g: Energy 420 kcal, Protein 12 g, Total sugars 22 g ...\nServing size 40 g")
    if txt and st.button("Decode text", disabled=prov is None):
        from src.extract import extract_from_text
        with st.spinner(f"Structuring the text with {prov}..."):
            try:
                label = extract_from_text(txt)
            except Exception as e:
                st.error(f"Extraction failed: {e}")
                label = None
        if label:
            render(label, decode_label(label))

with tab_barcode:
    code = st.text_input("Barcode (EAN-13 under the bars, usually starts with 890 for India)")
    if code and st.button("Look up"):
        with st.spinner("Fetching from Open Food Facts..."):
            prod = fetch_product(code.strip())
        if not prod:
            st.error("Not on Open Food Facts. Use a photo instead.")
        else:
            label = to_label(prod)
            imgs = label.get("images") or {}
            cols = st.columns(3)
            for col, kind in zip(cols, ("front", "ingredients", "nutrition")):
                if imgs.get(kind):
                    col.image(imgs[kind], caption=kind, use_container_width=True)
            dropped = drop_implausible(label)
            if dropped:
                st.warning("Ignored impossible Open Food Facts values (crowd-entry errors): " + ", ".join(dropped))
            st.caption("Open Food Facts is crowd-sourced; numbers can be off. Check against the photos.")
            render(label, decode_label(label))

with tab_examples:
    samples = load_samples()
    if not samples:
        st.info("Run `python eval/build_testset.py` once to pull 100 Indian products from Open Food Facts for this tab.")
    else:
        names = [f"{s.get('brand') or ''} {s.get('product_name') or s.get('barcode')}".strip() for s in samples]
        pick = st.selectbox("Pick a product", range(len(samples)), format_func=lambda i: names[i])
        label = samples[pick]
        render(label, decode_label(label))
