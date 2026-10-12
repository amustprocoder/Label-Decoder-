"""
Vision extraction: label photo(s) or pasted text -> the structured label dict that
src/rules/decoder.py consumes. The model only transcribes; every judgement lives in the
rules layer, which is what keeps verdicts reproducible and testable.
"""

from __future__ import annotations

from .llm import text_json, vision_json

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


def extract_from_images(images: list) -> dict:
    return _clean(vision_json(images, PROMPT_IMAGE, LABEL_SCHEMA, system=SYSTEM))


def extract_from_text(text: str) -> dict:
    return _clean(text_json(PROMPT_TEXT + text, LABEL_SCHEMA, system=SYSTEM))


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
    return d


def _f(x):
    try:
        return None if x in (None, "", "-") else float(x)
    except (TypeError, ValueError):
        return None
