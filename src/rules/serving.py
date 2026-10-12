"""
Serving-size and unit maths.

Indian labels declare nutrition per 100 g / 100 ml (mandatory under the FSS (Labelling and
Display) Regulations, 2020) and optionally per serve. Front-of-pack claims are almost always
on the per-100 g basis; what you actually eat is one serve. This module converts between them.
"""

from __future__ import annotations

TEASPOON_G = 4.0                 # one level teaspoon of sugar is about 4 g
WHO_FREE_SUGAR_10PCT_G = 50.0    # WHO: free sugars under 10% of a 2000 kcal day = 50 g
WHO_FREE_SUGAR_5PCT_G = 25.0     # WHO conditional recommendation: under 5% = 25 g
SODIUM_TO_SALT = 2.5             # salt (NaCl) = sodium x 2.5

# FSS (Labelling & Display) Regulations 2020 RDA table (adult, 2000 kcal basis), plus
# ICMR-NIN 2020 values where FSSAI gives none.
FSSAI_RDA = {
    "energy_kcal": 2000, "total_fat_g": 67, "saturated_fat_g": 22, "added_sugars_g": 50,
    "sodium_mg": 2000, "carbohydrate_g": 325,
    "protein_g": 54,          # ICMR-NIN 2020: 0.83 g/kg x 65 kg reference man
    "dietary_fibre_g": 30,    # ICMR-NIN 2020 adequate intake
}
KCAL_PER_G = {"protein_g": 4, "carbohydrate_g": 4, "total_fat_g": 9,
              "total_sugars_g": 4, "added_sugars_g": 4}

# Realistic single-sitting portion when the pack does not state one. Always surfaced as an assumption.
DEFAULT_SERVE_G = {
    "biscuit": 30, "cookie": 30, "chips": 30, "namkeen": 30, "chocolate": 25, "cereal": 30,
    "granola": 40, "health drink": 30, "malt": 30, "protein powder": 30, "juice": 200,
    "beverage": 250, "soft drink": 300, "energy drink": 250, "yogurt": 100, "curd": 100,
    "ice cream": 100, "noodles": 70, "bread": 50, "ketchup": 15, "sauce": 15, "jam": 15,
    "spread": 15, "bar": 40, "milk": 200, "default": 30,
}


def per_serving(value_per_100: float | None, serving_g: float | None) -> float | None:
    if value_per_100 is None or serving_g is None:
        return None
    return value_per_100 * serving_g / 100.0


def teaspoons(sugar_g: float | None) -> float | None:
    return None if sugar_g is None else sugar_g / TEASPOON_G


def pct_of_rda(value: float | None, key: str) -> float | None:
    rda = FSSAI_RDA.get(key)
    if value is None or not rda:
        return None
    return 100.0 * value / rda


def pct_energy_from(nutrient_g: float | None, energy_kcal: float | None, key: str) -> float | None:
    """Share of energy that a nutrient supplies (both values on the same basis)."""
    if nutrient_g is None or not energy_kcal:
        return None
    return 100.0 * nutrient_g * KCAL_PER_G[key] / energy_kcal


def sodium_from_salt(salt_g: float | None) -> float | None:
    return None if salt_g is None else salt_g * 1000.0 / SODIUM_TO_SALT


def pick_serving(label: dict) -> tuple[float | None, str]:
    """Return (serving_g, how we got it)."""
    s = label.get("serving_size_g")
    is_liquid = bool(label.get("is_liquid"))
    net = label.get("net_quantity_g")
    if s:
        s = float(s)
        implausible = (not is_liquid and s > 150) or (is_liquid and s > 1000) or (net and s > float(net) * 1.05)
        if not implausible:
            return s, "declared on pack"
        # e.g. a malt powder whose "serve" is 250 ml of prepared drink while nutrition is per 100 g powder
        label = dict(label)
        label["_ignored_serving"] = s
    cat = f"{label.get('category') or ''} {label.get('product_name') or ''}".lower()
    why = ("the pack declares no serve" if not label.get("_ignored_serving")
           else f"the declared serve ({label['_ignored_serving']:g}) does not fit a per-100 g panel, likely an as-prepared volume")
    for k, v in DEFAULT_SERVE_G.items():
        if k != "default" and k in cat:
            return float(v), f"assumed typical {k} portion of {v} g; {why}"
    return float(DEFAULT_SERVE_G["default"]), f"assumed 30 g portion; {why}"
