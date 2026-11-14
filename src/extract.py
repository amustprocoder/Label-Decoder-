"""
Vision extraction: label photo(s) or pasted text -> the structured label dict that
src/rules/decoder.py consumes. The model only transcribes; every judgement lives in the
rules layer, which is what keeps verdicts reproducible and testable.
"""

from __future__ import annotations

import copy

from .llm import provider, text_json, vision_json

NUTRIENT_KEYS = ["energy_kcal", "protein_g", "carbohydrate_g", "total_sugars_g", "added_sugars_g",
                 "dietary_fibre_g", "total_fat_g", "saturated_fat_g", "trans_fat_g", "cholesterol_mg",
                 "sodium_mg", "salt_g"]

_NUM_OR_NULL = {"type": ["number", "null"]}

LABEL_SCHEMA = {
    "type": "object",
    "properties": {
        "product_name": {"type": ["string", "null"]},
        "brand": {"type": ["string", "null"]},
        "category": {"type": ["string", "null"],
                     "description": "short category e.g. biscuit, chips, health drink powder, juice, cereal, chocolate, noodles"},
        "barcode": {"type": ["string", "null"]},
        "net_quantity_g": _NUM_OR_NULL,
        "serving_size_g": {"type": ["number", "null"], "description": "declared serve in g or ml; null if the pack gives none"},
        "servings_per_pack": _NUM_OR_NULL,
        "is_liquid": {"type": "boolean"},
        "basis": {"type": "string", "enum": ["per 100g", "per 100ml", "per serving", "unknown"]},
        "as_prepared_note": {"type": ["string", "null"],
                             "description": "if values are 'as prepared' / 'with 200 ml milk', copy that wording"},
        "per_100": {"type": "object",
                    "properties": {k: _NUM_OR_NULL for k in NUTRIENT_KEYS},
                    "required": NUTRIENT_KEYS, "additionalProperties": False},
        "per_serving_declared": {"type": "object",
                                 "properties": {k: _NUM_OR_NULL for k in NUTRIENT_KEYS},
                                 "required": NUTRIENT_KEYS, "additionalProperties": False},
        "ingredients_text": {"type": "string", "description": "verbatim ingredient list, keep brackets and % values"},
        "ingredients": {"type": "array",
                        "items": {"type": "object",
                                  "properties": {"name": {"type": "string"},
                                                 "percent": _NUM_OR_NULL,
                                                 "nested": {"type": "boolean"}},
                                  "required": ["name", "percent", "nested"], "additionalProperties": False}},
        "front_of_pack_claims": {"type": "array", "items": {"type": "string"},
                                 "description": "every marketing phrase on the front: 'no added sugar', 'high protein', 'immunity', 'real fruit'..."},
        "language": {"type": "string", "description": "label language(s) seen, e.g. en, hi, en+hi"},
        "legibility": {"type": "string", "enum": ["good", "partial", "poor"]},
        "notes": {"type": "string", "description": "anything unreadable or ambiguous; empty string if none"},
    },
    "required": ["product_name", "brand", "category", "barcode", "net_quantity_g", "serving_size_g",
                 "servings_per_pack", "is_liquid", "basis", "as_prepared_note", "per_100",
                 "per_serving_declared", "ingredients_text", "ingredients", "front_of_pack_claims",
                 "language", "legibility", "notes"],
    "additionalProperties": False,
}

SYSTEM = (
    "You transcribe Indian packaged-food labels into JSON. Transcribe exactly what is printed; never infer "
    "or 'correct' numbers. If the nutrition table is per serving only, fill per_serving_declared and compute "
    "per_100 only when serving size is printed (and say so in notes). Sodium: if the pack prints salt, fill "
    "salt_g and leave sodium_mg null. Units: convert kJ to kcal only if kcal is absent (divide by 4.184). "
    "Ingredients: keep label order; put bracketed sub-ingredients as separate items with nested=true right "
    "after their parent; capture any % values. Front-of-pack claims: list every marketing phrase, including "
    "words like healthy, natural, immunity, energy, real fruit, multigrain, baked, no maida, protein."
)

PROMPT_IMAGE = ("Transcribe this label (one or more photos of the same pack: front, ingredients, nutrition "
                "table). Return the JSON only.")
PROMPT_TEXT = "Here is label text pasted by a user. Structure it as JSON. Text:\n\n"


# Gemini blocks its own answer (finishReason RECITATION) when asked to copy an ingredient list word for word:
# published labels look like "existing text" to its filter. Tested on real pack photos: with the verbatim
# `ingredients_text` field every model refused, without it every model answered and the numbers matched.
# So Gemini is asked for the ingredients only as separate items, which is what the rules layer reads anyway.
GEMINI_SYSTEM = (
    "You read Indian packaged-food labels and fill in a structured form. Use only numbers printed on the pack; never "
    "guess or 'correct' them. If the nutrition table is per serving only, fill per_serving_declared and compute per_100 "
    "only when the serving size is printed (say so in notes). If the pack prints salt, fill salt_g and leave sodium_mg "
    "null. Convert kJ to kcal only if kcal is absent (divide by 4.184). List each ingredient as its own item in label "
    "order, bracketed sub-ingredients as separate items with nested=true right after their parent, with % values when "
    "printed. List every marketing phrase on the front (healthy, natural, immunity, energy, real fruit, multigrain, "
    "baked, no maida, protein...). Use null when a value is not printed."
)


def _gemini_schema() -> dict:
    s = copy.deepcopy(LABEL_SCHEMA)
    s["properties"].pop("ingredients_text")
    s["required"] = [k for k in s["required"] if k != "ingredients_text"]
    return s


def _ask() -> tuple[dict, str]:
    return (_gemini_schema(), GEMINI_SYSTEM) if provider() == "gemini" else (LABEL_SCHEMA, SYSTEM)


def extract_from_images(images: list) -> dict:
    schema, system = _ask()
    return _clean(vision_json(images, PROMPT_IMAGE, schema, system=system))


def extract_from_text(text: str) -> dict:
    schema, system = _ask()
    return _clean(text_json(PROMPT_TEXT + text, schema, system=system))


def _join_ingredients(items: list) -> str:
    """Rebuild a readable ingredient line from the item list: 'Wheat flour (68%), Sugar, Syrup (Sugar, Citric acid)'."""
    groups: list[tuple[str, list[str]]] = []          # (ingredient, its bracketed sub-ingredients)
    for it in items:
        name = (it.get("name") or "").strip()
        if not name:
            continue
        if _f(it.get("percent")) is not None:
            name += f" {_f(it['percent']):g}%"
        if it.get("nested") and groups:
            groups[-1][1].append(name)
        else:
            groups.append((name, []))
    return ", ".join(parent + (f" ({', '.join(subs)})" if subs else "") for parent, subs in groups)


def _clean(d: dict) -> dict:
    """Normalise a model response: per-serving-only tables, missing dicts, stray strings."""
    d.setdefault("per_100", {})
    d.setdefault("per_serving_declared", {})
    d.setdefault("ingredients", [])
    d.setdefault("front_of_pack_claims", [])
    per100 = {k: _f(d["per_100"].get(k)) for k in NUTRIENT_KEYS}
    serve = {k: _f(d["per_serving_declared"].get(k)) for k in NUTRIENT_KEYS}
    s = _f(d.get("serving_size_g"))
    if all(v is None for v in per100.values()) and s and any(v is not None for v in serve.values()):
        per100 = {k: (None if v is None else v * 100.0 / s) for k, v in serve.items()}
        d["notes"] = (d.get("notes") or "") + " per_100 derived from per-serving table."
    d["per_100"] = per100
    d["per_serving_declared"] = serve
    d["serving_size_g"] = s
    if not d.get("ingredients_text") and d["ingredients"]:
        d["ingredients_text"] = _join_ingredients(d["ingredients"])
    return d


def _f(x):
    try:
        return None if x in (None, "", "-") else float(x)
    except (TypeError, ValueError):
        return None
