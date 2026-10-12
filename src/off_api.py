"""
Open Food Facts lookup: barcode -> label dict in the same shape as src/extract.py produces.

Used two ways:
  - In the app, as a no-camera fallback ("type the barcode").
  - In eval/, as the ground-truth side of the extraction accuracy test.

OFF data is crowd-sourced; numbers can be wrong by a decimal place (salt_100g = 295 happens).
`sanity()` flags rows that cannot be right so the eval does not score the model against junk.
"""

from __future__ import annotations

import requests

UA = {"User-Agent": "IndianLabelDecoder/0.1 (student project; github.com/omrana)"}
BASE = "https://world.openfoodfacts.org/api/v2"
FIELDS = ("code,product_name,brands,quantity,serving_size,nutrition_data_per,ingredients_text,"
          "ingredients_text_en,nutriments,categories_tags,selected_images,image_front_url,"
          "image_ingredients_url,image_nutrition_url,labels_tags,lang,countries_tags")

NUTRIMENT_MAP = {
    "energy_kcal": "energy-kcal_100g", "protein_g": "proteins_100g", "carbohydrate_g": "carbohydrates_100g",
    "total_sugars_g": "sugars_100g", "added_sugars_g": "added-sugars_100g", "dietary_fibre_g": "fiber_100g",
    "total_fat_g": "fat_100g", "saturated_fat_g": "saturated-fat_100g", "trans_fat_g": "trans-fat_100g",
    "cholesterol_mg": "cholesterol_100g", "sodium_mg": "sodium_100g", "salt_g": "salt_100g",
}
LIQUID_HINTS = ("beverage", "juice", "drink", "milk", "water", "soda", "cola", "lassi", "buttermilk", "tea", "coffee")


def fetch_product(barcode: str) -> dict | None:
    r = requests.get(f"{BASE}/product/{barcode}.json", params={"fields": FIELDS}, headers=UA, timeout=30)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    data = r.json()
    if data.get("status") == 0:
        return None
    return data.get("product")


def search_india(page: int = 1, page_size: int = 100, extra: dict | None = None) -> dict:
    """
    India products with completed nutrition facts and ingredients, most-scanned first.
    Uses the legacy cgi/search.pl endpoint: the v2 /search endpoint returns 503 for tag queries
    at the moment (checked 2026-10-02). OFF allows ~10 search calls per minute; callers must pace.
    """
    params = {"action": "process", "json": 1, "page_size": page_size, "page": page,
              "fields": FIELDS,          # no sort_by: unique_scans_n makes the endpoint 503
              "tagtype_0": "countries", "tag_contains_0": "contains", "tag_0": "india",
              "tagtype_1": "states", "tag_contains_1": "contains", "tag_1": "nutrition-facts-completed",
              "tagtype_2": "states", "tag_contains_2": "contains", "tag_2": "ingredients-completed"}
    params.update(extra or {})
    r = requests.get("https://world.openfoodfacts.org/cgi/search.pl", params=params, headers=UA, timeout=90)
    r.raise_for_status()
    return r.json()


def search_codes_india(page: int = 1, page_size: int = 100) -> tuple[list[str], int]:
    """
    Barcodes of India products with completed nutrition facts and ingredients, via the
    search-a-licious API (search.openfoodfacts.org), which stays up when cgi/search.pl 503s.
    Returns (codes, total_count). Full product data then comes from fetch_product() per code,
    because search results carry only the front image, not the nutrition / ingredient photos.
    """
    q = ('countries_tags:"en:india" AND states_tags:"en:nutrition-facts-completed" '
         'AND states_tags:"en:ingredients-completed"')
    r = requests.get("https://search.openfoodfacts.org/search",
                     params={"q": q, "page": page, "page_size": page_size, "fields": "code"},
                     headers=UA, timeout=60)
    r.raise_for_status()
    data = r.json()
    return [h["code"] for h in data.get("hits", []) if h.get("code")], int(data.get("count") or 0)


def _serving_g(s: str | None) -> float | None:
    if not s:
        return None
    import re
    m = re.search(r"(\d+(?:\.\d+)?)\s*(g|ml|gm|gms|grams?)", s.lower())
    if m:
        return float(m.group(1))
    m = re.search(r"\d+(?:\.\d+)?", s)
    return float(m.group(0)) if m else None


def to_label(p: dict) -> dict:
    """OFF product -> decoder label dict."""
    n = p.get("nutriments") or {}
    per100 = {}
    for k, off in NUTRIMENT_MAP.items():
        v = n.get(off)
        if v is None:
            continue
        v = float(v)
        if k in ("sodium_mg", "cholesterol_mg"):
            v = v * 1000.0          # OFF stores g
        per100[k] = v
    cats = " ".join(p.get("categories_tags") or [])
    solid_words = ("powder", "chocolate", "malt", "mix", "dried", "candies", "candy", "biscuit", "snack", "cereal")
    is_liquid = (p.get("nutrition_data_per") == "100ml") or (
        any(h in cats for h in LIQUID_HINTS) and not any(w in cats for w in solid_words))
    imgs = p.get("selected_images") or {}

    def img(kind: str) -> str | None:
        d = (imgs.get(kind) or {}).get("display") or {}
        return d.get("en") or next(iter(d.values()), None) or p.get(f"image_{kind}_url")

    serving_str = (p.get("serving_size") or "").lower()
    serving_g = _serving_g(serving_str)
    if serving_g and not is_liquid and "ml" in serving_str:
        serving_g = None            # an as-prepared volume (malt powders, mixes) does not fit a per-100 g panel
    return {
        "product_name": p.get("product_name"), "brand": p.get("brands"), "barcode": p.get("code"),
        "category": (cats.split("en:")[-1].replace("-", " ") if cats else None),
        "net_quantity_g": _serving_g(p.get("quantity")), "serving_size_g": serving_g,
        "servings_per_pack": None, "is_liquid": is_liquid,
        "basis": "per 100ml" if is_liquid else "per 100g",
        "per_100": per100,
        "ingredients_text": p.get("ingredients_text_en") or p.get("ingredients_text") or "",
        "ingredients": [],
        "front_of_pack_claims": [t.split(":")[-1].replace("-", " ") for t in (p.get("labels_tags") or [])],
        "images": {"front": img("front"), "ingredients": img("ingredients"), "nutrition": img("nutrition")},
        "source": "open_food_facts",
    }


PLAUSIBLE_MAX = {"energy_kcal": 900, "protein_g": 100, "carbohydrate_g": 100, "total_sugars_g": 100, "added_sugars_g": 100,
                 "dietary_fibre_g": 100, "total_fat_g": 100, "saturated_fat_g": 100, "trans_fat_g": 50,
                 "cholesterol_mg": 3000, "sodium_mg": 20000, "salt_g": 50}


def drop_implausible(label: dict) -> list[str]:
    """Remove per-100 values that cannot be real (decimal-point errors in crowd data). Returns what was dropped."""
    p = label.get("per_100") or {}
    dropped = []
    for k, mx in PLAUSIBLE_MAX.items():
        v = p.get(k)
        if v is not None and (v < 0 or v > mx):
            dropped.append(f"{k}={v:g}")
            p[k] = None
    if p.get("total_sugars_g") is not None and p.get("carbohydrate_g") is not None and p["total_sugars_g"] > p["carbohydrate_g"] + 1:
        dropped.append(f"total_sugars_g={p['total_sugars_g']:g} > carbohydrate")
        p["total_sugars_g"] = None
    label["per_100"] = p
    return dropped


def sanity(label: dict) -> list[str]:
    """Return a list of reasons this OFF row is not trustworthy as ground truth."""
    p = label.get("per_100") or {}
    bad = []
    for k in ("total_sugars_g", "carbohydrate_g", "protein_g", "total_fat_g", "dietary_fibre_g", "saturated_fat_g"):
        v = p.get(k)
        if v is not None and (v < 0 or v > 100):
            bad.append(f"{k}={v} out of 0-100")
    if p.get("total_sugars_g") is not None and p.get("carbohydrate_g") is not None and p["total_sugars_g"] > p["carbohydrate_g"] + 1:
        bad.append("sugars > carbohydrate")
    if p.get("salt_g") is not None and p["salt_g"] > 50:
        bad.append(f"salt_g={p['salt_g']} implausible")
    if p.get("sodium_mg") is not None and p["sodium_mg"] > 20000:
        bad.append(f"sodium_mg={p['sodium_mg']} implausible")
    e = p.get("energy_kcal")
    if e is not None and (e < 0 or e > 900):
        bad.append(f"energy_kcal={e} out of range")
    macro = sum(p.get(k) or 0 for k in ("protein_g", "carbohydrate_g", "total_fat_g"))
    if e and macro and (macro * 4 > e * 2.5 or (macro > 10 and e < 10)):
        bad.append("energy inconsistent with macros")
    txt = label.get("ingredients_text") or ""
    if not txt:
        bad.append("no ingredient text")
    elif len(txt) > 60 and txt.count(",") + txt.count(";") < 2:
        bad.append("ingredient text is raw OCR, not a list")
    return bad
