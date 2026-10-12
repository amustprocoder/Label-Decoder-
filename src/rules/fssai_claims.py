"""
FSSAI claim rules: what a front-of-pack claim legally demands, versus what it implies.

Primary source: Food Safety and Standards (Advertising and Claims) Regulations, 2018,
Schedule I (nutrient content claims) and Regulations 4-9 (general conditions, "natural",
non-addition claims, comparative claims). Thresholds are per 100 g for solids and per 100 ml
for liquids. These regulations are amended from time to time; treat the numbers below as the
2018 baseline and re-verify against the current gazette before quoting them in public.

Each rule returns a ClaimCheck: the legal test, whether the pack passes it, and the
per-serving reality that the claim quietly leaves out.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .serving import FSSAI_RDA, pct_energy_from, pct_of_rda, per_serving

REG = "FSS (Advertising & Claims) Regulations 2018"

# Schedule I thresholds: claim -> (solid limit, liquid limit, unit, comparator)
SCHEDULE_I = {
    "low energy":        {"key": "energy_kcal",     "solid": 40,    "liquid": 20,   "unit": "kcal", "op": "<="},
    "energy free":       {"key": "energy_kcal",     "solid": 4,     "liquid": 4,    "unit": "kcal", "op": "<="},
    "low fat":           {"key": "total_fat_g",     "solid": 3,     "liquid": 1.5,  "unit": "g",    "op": "<="},
    "fat free":          {"key": "total_fat_g",     "solid": 0.5,   "liquid": 0.5,  "unit": "g",    "op": "<="},
    "low saturated fat": {"key": "saturated_fat_g", "solid": 1.5,   "liquid": 0.75, "unit": "g",    "op": "<="},
    "saturated fat free":{"key": "saturated_fat_g", "solid": 0.1,   "liquid": 0.1,  "unit": "g",    "op": "<="},
    "trans fat free":    {"key": "trans_fat_g",     "solid": 0.2,   "liquid": 0.2,  "unit": "g",    "op": "<="},
    "low cholesterol":   {"key": "cholesterol_mg",  "solid": 20,    "liquid": 10,   "unit": "mg",   "op": "<="},
    "cholesterol free":  {"key": "cholesterol_mg",  "solid": 5,     "liquid": 5,    "unit": "mg",   "op": "<="},
    "low sugar":         {"key": "total_sugars_g",  "solid": 5,     "liquid": 2.5,  "unit": "g",    "op": "<="},
    "sugar free":        {"key": "total_sugars_g",  "solid": 0.5,   "liquid": 0.5,  "unit": "g",    "op": "<="},
    "low sodium":        {"key": "sodium_mg",       "solid": 120,   "liquid": 120,  "unit": "mg",   "op": "<="},
    "very low sodium":   {"key": "sodium_mg",       "solid": 40,    "liquid": 40,   "unit": "mg",   "op": "<="},
    "sodium free":       {"key": "sodium_mg",       "solid": 5,     "liquid": 5,    "unit": "mg",   "op": "<="},
    "source of fibre":   {"key": "dietary_fibre_g", "solid": 3,     "liquid": 1.5,  "unit": "g",    "op": ">="},
    "high fibre":        {"key": "dietary_fibre_g", "solid": 6,     "liquid": 3,    "unit": "g",    "op": ">="},
    # protein is defined as a share of RDA, handled separately
    "source of protein": {"key": "protein_g", "pct_rda_solid": 10, "pct_rda_liquid": 5, "pct_rda_serving": 10, "op": ">="},
    "high protein":      {"key": "protein_g", "pct_rda_solid": 20, "pct_rda_liquid": 10, "pct_rda_serving": 20, "op": ">="},
}

# How front-of-pack wording maps to a Schedule I claim (first match wins, most specific first)
CLAIM_PATTERNS: list[tuple[str, str]] = [
    (r"\bno\s*added\s*sugars?\b|\bwithout\s*added\s*sugars?\b|\bzero\s*added\s*sugar\b|\bunsweetened\b", "no added sugar"),
    (r"\bsugar[\s-]*free\b|\bzero\s*sugar\b|\b0\s*%?\s*sugar\b|\bno\s*sugar\b", "sugar free"),
    (r"\blow\s*(?:in\s*)?sugar\b|\bless\s*sugar\b|\breduced\s*sugar\b|\blite\b|\blight\b", "low sugar"),
    (r"\bhigh\s*(?:in\s*)?protein\b|\bprotein[\s-]*rich\b|\brich\s*in\s*protein\b|\bprotein\s*power\b", "high protein"),
    (r"\bsource\s*of\s*protein\b|\bcontains\s*protein\b|\bwith\s*protein\b|\b\d+\s*g\s*(?:of\s*)?protein\b|\bprotein\b", "source of protein"),
    (r"\bhigh\s*(?:in\s*)?fib(?:re|er)\b|\bfib(?:re|er)[\s-]*rich\b|\brich\s*in\s*fib(?:re|er)\b", "high fibre"),
    (r"\bsource\s*of\s*fib(?:re|er)\b|\bwith\s*fib(?:re|er)\b|\bfib(?:re|er)\b", "source of fibre"),
    (r"\bfat[\s-]*free\b|\bzero\s*fat\b|\b0\s*%?\s*fat\b|\bno\s*fat\b", "fat free"),
    (r"\blow\s*(?:in\s*)?fat\b|\bless\s*fat\b|\breduced\s*fat\b", "low fat"),
    (r"\b(?:zero|no|0\s*g?)\s*trans[\s-]*fat\b|\btrans[\s-]*fat[\s-]*free\b", "trans fat free"),
    (r"\b(?:zero|no|0)\s*cholesterol\b|\bcholesterol[\s-]*free\b", "cholesterol free"),
    (r"\blow\s*cholesterol\b", "low cholesterol"),
    (r"\bvery\s*low\s*sodium\b", "very low sodium"),
    (r"\blow\s*(?:in\s*)?(?:sodium|salt)\b|\bless\s*salt\b|\breduced\s*salt\b", "low sodium"),
    (r"\bsodium[\s-]*free\b|\bsalt[\s-]*free\b|\bno\s*(?:added\s*)?salt\b", "sodium free"),
    (r"\blow\s*(?:calorie|cal|energy)\b|\bcalorie[\s-]*smart\b|\bdiet\b", "low energy"),
    (r"\b(?:zero|0)\s*(?:calorie|cal)\b|\bcalorie[\s-]*free\b", "energy free"),
]

# Claims FSSAI regulates qualitatively (no number to check) but which routinely mislead
SOFT_CLAIM_PATTERNS: list[tuple[str, str]] = [
    (r"\b100\s*%\s*natural\b|\ball[\s-]*natural\b|\bnatural\b", "natural"),
    (r"\breal\s*fruit\b|\bmade\s*with\s*(?:real\s*)?fruit\b|\bfruit\s*juice\b|\bfruit\s*power\b", "real fruit"),
    (r"\bmulti[\s-]*grain\b|\b\d+\s*grains?\b", "multigrain"),
    (r"\bwhole[\s-]*(?:grain|wheat)\b|\batta\b", "whole grain"),
    (r"\bimmun", "immunity"),
    (r"\benergy\b|\bstamina\b|\bvitality\b|\bstrength\b|\btaller\b|\bstronger\b|\bsharper\b|\bgrowth\b|\bbrain\b", "energy / growth"),
    (r"\bhealthy\b|\bhealth\s*drink\b|\bnutritious\b|\bnutrition\b|\bwholesome\b|\bgoodness\b", "healthy"),
    (r"\bbaked\b(?:\s*not\s*fried)?", "baked"),
    (r"\bno\s*maida\b|\bmaida[\s-]*free\b", "no maida"),
    (r"\bno\s*preservatives?\b|\bpreservative[\s-]*free\b", "no preservatives"),
    (r"\bno\s*(?:added\s*)?(?:msg|monosodium)\b", "no msg"),
    (r"\bno\s*(?:artificial\s*)?colou?rs?\b|\bno\s*artificial\s*flavou?rs?\b", "no artificial"),
    (r"\bpalm\s*oil\s*free\b|\bno\s*palm\s*oil\b", "no palm oil"),
    (r"\bgluten[\s-]*free\b", "gluten free"),
    (r"\bketo\b|\bvegan\b|\bplant[\s-]*based\b|\bclean\s*label\b|\bsuperfood\b", "lifestyle"),
    (r"\bdoctor|\bdietitian|\bnutritionist|\bclinically|\bscientifically|\brecommended\b", "authority"),
]


@dataclass
class ClaimCheck:
    claim_text: str
    claim_type: str
    legal_test: str
    threshold: float | None
    actual_per_100: float | None
    passes_legal_test: bool | None       # None = cannot evaluate from the label
    per_serving_value: float | None
    per_serving_pct_rda: float | None
    verdict: str                          # "holds" | "fails" | "legal but misleading" | "unverifiable"
    explanation: str
    rule_ref: str = REG
    extra: dict = field(default_factory=dict)


def detect_claims(texts: list[str]) -> list[tuple[str, str, str]]:
    """Return [(raw text, claim_type, kind)] with kind = 'schedule' or 'soft'."""
    out: list[tuple[str, str, str]] = []
    for raw in texts or []:
        t = (raw or "").lower().strip()
        if not t:
            continue
        matched = False
        for pat, ctype in CLAIM_PATTERNS:
            if re.search(pat, t):
                out.append((raw, ctype, "schedule"))
                matched = True
                break
        for pat, ctype in SOFT_CLAIM_PATTERNS:
            if re.search(pat, t):
                out.append((raw, ctype, "soft"))
                matched = True
        if not matched:
            out.append((raw, "other", "soft"))
    # de-duplicate on (type) keeping first wording
    seen, uniq = set(), []
    for raw, ctype, kind in out:
        if (ctype, kind) in seen:
            continue
        seen.add((ctype, kind))
        uniq.append((raw, ctype, kind))
    return uniq


def _cmp(op: str, actual: float, limit: float) -> bool:
    return actual <= limit if op == "<=" else actual >= limit


def check_schedule_claim(raw: str, ctype: str, per100: dict, serving_g: float | None,
                         is_liquid: bool, energy_per_100: float | None) -> ClaimCheck:
    rule = SCHEDULE_I.get(ctype)
    if ctype == "no added sugar":
        return ClaimCheck(raw, ctype, "Reg 8 non-addition claim: no added sugars, no sugar-substituting ingredients "
                          "(concentrated fruit juice, dried fruit paste), sugar not increased by processing",
                          None, per100.get("total_sugars_g"), None, per_serving(per100.get("total_sugars_g"), serving_g),
                          None, "unverifiable", "Evaluated against the ingredient list, see flags.")
    if not rule:
        return ClaimCheck(raw, ctype, "no numeric test", None, None, None, None, None, "unverifiable",
                          "No Schedule I threshold for this wording.")
    key = rule["key"]
    actual = per100.get(key)
    if actual is None:
        return ClaimCheck(raw, ctype, f"Schedule I: {ctype}", None, None, None, None, None, "unverifiable",
                          f"The label does not declare {key.replace('_', ' ')} per 100 {'ml' if is_liquid else 'g'}.")
    serve_val = per_serving(actual, serving_g)
    serve_pct = pct_of_rda(serve_val, key)

    if key == "protein_g":
        rda = FSSAI_RDA["protein_g"]
        pct_limit = rule["pct_rda_liquid"] if is_liquid else rule["pct_rda_solid"]
        pct_100 = 100.0 * actual / rda
        passes_100 = pct_100 >= pct_limit
        passes_serve = serve_pct is not None and serve_pct >= rule["pct_rda_serving"]
        legal = (f"Schedule I: at least {pct_limit}% of protein RDA ({rda} g) per 100 {'ml' if is_liquid else 'g'}, "
                 f"or {rule['pct_rda_serving']}% per serving")
        if passes_100 and passes_serve:
            verdict, expl = "holds", f"{actual:g} g/100 is {pct_100:.0f}% of RDA; one serve gives {serve_val:.1f} g ({serve_pct:.0f}% of RDA)."
        elif passes_100 and not passes_serve:
            verdict = "legal but misleading"
            expl = (f"Passes on the per-100 g basis ({pct_100:.0f}% of RDA) but one {serving_g:g} g serve delivers only "
                    f"{serve_val:.1f} g protein, {serve_pct:.0f}% of a day's need. The claim is priced per 100 g; you eat per serve.")
        else:
            verdict, expl = "fails", f"{actual:g} g/100 is only {pct_100:.0f}% of RDA; below the {pct_limit}% bar."
        return ClaimCheck(raw, ctype, legal, pct_limit, actual, passes_100, serve_val, serve_pct, verdict, expl,
                          extra={"pct_rda_per_100": round(pct_100, 1)})

    limit = rule["liquid"] if is_liquid else rule["solid"]
    passes = _cmp(rule["op"], actual, limit)
    legal = f"Schedule I: {ctype} means {rule['op']} {limit:g} {rule['unit']} per 100 {'ml' if is_liquid else 'g'}"
    if ctype == "low saturated fat" and passes and energy_per_100:
        share = pct_energy_from(actual, energy_per_100, "total_fat_g")
        if share and share > 10:
            passes = False
            legal += " and not more than 10% of energy from saturated fat"
    if ctype == "cholesterol free" and passes:
        extra_note = " (Reg 4: a claim that all foods of this type share, such as cholesterol-free vegetable oil, is prohibited as misleading)"
    else:
        extra_note = ""
    if passes:
        verdict = "holds"
        expl = f"{actual:g} {rule['unit']}/100 meets the {limit:g} {rule['unit']} bar.{extra_note}"
        if ctype in ("sugar free", "low sugar") and serve_val is not None:
            expl += f" One serve still carries {serve_val:.1f} g sugar."
    else:
        verdict = "fails"
        expl = f"{actual:g} {rule['unit']}/100 vs the {limit:g} {rule['unit']} bar for '{ctype}'."
    return ClaimCheck(raw, ctype, legal, limit, actual, passes, serve_val, serve_pct, verdict, expl)
