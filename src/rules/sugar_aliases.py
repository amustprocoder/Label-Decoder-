"""
Sugar aliases: every name under which added sugar hides on an Indian ingredient list.

Why this exists: FSSAI only requires ingredients in descending order of weight.
A pack can list "sugar", "liquid glucose", "invert syrup" and "dextrose" as four
separate items so that none of them tops the list, even when together they are
the #1 ingredient. This module collapses them back into one line.

Tiers:
  ADDED_SUGAR  - counts as added / free sugar under FSSAI and WHO definitions
  SUGAR_LIKE   - not legally "sugar" but digests like it (maltodextrin, maida)
  SWEETENER    - non-nutritive or polyol sweeteners (flags "sugar free" products)
  INTRINSIC    - naturally occurring sugar that is NOT added (whole fruit, milk)
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# canonical name -> regex patterns (matched case-insensitively on one ingredient line)
ADDED_SUGAR: dict[str, list[str]] = {
    "sugar (sucrose)": [
        r"\bsugar\b(?!\s*free)", r"\bsucrose\b", r"\bcane\s*sugar\b", r"\bwhite\s*sugar\b",
        r"\brefined\s*sugar\b", r"\bbrown\s*sugar\b", r"\bdemerara\b", r"\bcastor\s*sugar\b",
        r"\bicing\s*sugar\b", r"\bpowdered\s*sugar\b", r"\braw\s*sugar\b", r"\bkhandsari\b",
        r"\bbura\b", r"\bmisri\b", r"\brock\s*sugar\b", r"\bcheeni\b", r"\bshakkar\b",
        r"\bevaporated\s*cane\s*juice\b", r"\bsucanat\b", r"\bpanela\b", r"\bcoconut\s*sugar\b",
        r"\bpalm\s*sugar\b", r"\bsugar\s*syrup\b", r"\bsugar\s*crystals?\b",
    ],
    "jaggery (gur)": [r"\bjaggery\b", r"\bgur\b", r"\bgud\b"],
    "liquid glucose / glucose syrup": [
        r"\bliquid\s*glucose\b", r"\bglucose\s*syrup\b", r"\bglucose\b(?!\s*free)",
        r"\bcorn\s*syrup\b", r"\bisoglucose\b",
    ],
    "dextrose": [r"\bdextrose\b"],
    "fructose": [
        r"\bfructose\b(?![\s-]*oligo)", r"\bhigh[\s-]*fructose\s*corn\s*syrup\b", r"\bhfcs\b",
    ],
    "invert sugar / invert syrup": [r"\binvert(?:ed)?\s*(?:sugar|syrup)\b", r"\binvert\b"],
    "maltose / malt extract": [
        r"\bmaltose\b", r"\bmalt\s*syrup\b", r"\bmalt\s*extract\b", r"\bbarley\s*malt\b",
        r"\bmalted\s*barley\s*extract\b",
    ],
    "honey": [r"\bhoney\b", r"\bshahad\b"],
    "molasses / treacle": [r"\bmolasses\b", r"\btreacle\b", r"\bgolden\s*syrup\b"],
    "fruit juice concentrate": [
        r"\b(?:fruit|apple|grape|pear|orange|pineapple|mango|date|lemon|lime)\s*(?:juice\s*)?concentrate\b",
        r"\bconcentrated\s*(?:fruit|apple|grape)\s*juice\b", r"\bfruit\s*syrup\b",
    ],
    "dried fruit paste / date paste": [
        r"\bdate\s*(?:paste|syrup|powder)\b", r"\bdried\s*fruit\s*paste\b", r"\bfig\s*paste\b",
        r"\braisin\s*paste\b",          # whole dates / raisins as an ingredient are intrinsic, not flagged
    ],
    "syrups (agave / maple / rice)": [
        r"\bagave\b", r"\bmaple\s*syrup\b", r"\brice\s*syrup\b", r"\btapioca\s*syrup\b",
        r"\bcoconut\s*nectar\b",
    ],
    "lactose (added)": [r"\blactose\b"],
    "galactose / trehalose": [r"\bgalactose\b", r"\btrehalose\b"],
    "sweetened condensed milk": [r"\bcondensed\s*milk\b"],
    "caramel": [r"\bcaramel\b(?!\s*colou?r)"],
    "chocolate / choco chips (contain sugar)": [
        r"\bchoco(?:late)?\s*chips?\b", r"\bmilk\s*chocolate\b", r"\bcompound\s*chocolate\b",
    ],
    "jam / fruit filling (contains sugar)": [r"\bjam\b", r"\bfruit\s*filling\b", r"\bfruit\s*jelly\b"],
}

SUGAR_LIKE: dict[str, list[str]] = {
    "maltodextrin (high-GI, not counted as sugar)": [r"\bmalto\s*dextrine?\b"],
    "dextrin": [r"\bdextrin\b"],
    "modified starch": [r"\bmodified\s*(?:corn|tapioca|food|maize)?\s*starch\b", r"\bins\s*14\d\d\b"],
    "refined wheat flour (maida)": [r"\brefined\s*wheat\s*flour\b", r"\bmaida\b"],
    "polydextrose": [r"\bpolydextrose\b"],
}

SWEETENER: dict[str, list[str]] = {
    "sucralose (INS 955)": [r"\bsucralose\b", r"\b955\b"],
    "acesulfame K (INS 950)": [r"\bacesulfame\b", r"\bace[\s-]*k\b", r"\b950\b"],
    "aspartame (INS 951)": [r"\baspartame\b", r"\b951\b"],
    "saccharin (INS 954)": [r"\bsaccharin\b", r"\b954\b"],
    "steviol glycosides (INS 960)": [r"\bstevi", r"\brebaudioside\b", r"\b960\b"],
    "sorbitol (INS 420) - polyol": [r"\bsorbitol\b", r"\b420\b"],
    "maltitol (INS 965) - polyol": [r"\bmaltitol\b", r"\b965\b"],
    "xylitol (INS 967) - polyol": [r"\bxylitol\b", r"\b967\b"],
    "erythritol (INS 968) - polyol": [r"\berythritol\b", r"\b968\b"],
    "isomalt (INS 953) - polyol": [r"\bisomalt\b", r"\b953\b"],
    "monk fruit (mogrosides)": [r"\bmonk\s*fruit\b", r"\bluo\s*han\b", r"\bmogroside"],
    "neotame / advantame (INS 961/969)": [r"\bneotame\b", r"\badvantame\b", r"\b961\b", r"\b969\b"],
}

POLYOLS = {"sorbitol (INS 420) - polyol", "maltitol (INS 965) - polyol", "xylitol (INS 967) - polyol",
           "erythritol (INS 968) - polyol", "isomalt (INS 953) - polyol"}

# Looks sugary but is a whole food: never flagged as added sugar on its own.
INTRINSIC: list[str] = [
    r"\bwhole\s*fruit\b", r"\bfruit\s*pulp\b", r"\bfruit\s*pieces?\b", r"\bmilk\s*solids\b",
    r"\bskimmed?\s*milk\b", r"^milk$", r"\bbanana\b", r"\bmango\s*pulp\b", r"\btomato\b",
    r"\bfruit\s*juice\b(?!\s*concentrate)",
]
_SUGAR_WORDS = [r"\bsugar\b", r"\bsyrup\b", r"\bconcentrate\b", r"\bsweetened\b", r"\bcondensed\b"]

POLYOL_LAXATIVE_NOTE = (
    "FSSAI (Food Additives) rules require a laxative-effect advisory on foods with polyols above "
    "roughly 10 percent. A sugar-free product built on maltitol or sorbitol is not a free lunch."
)


@dataclass
class SugarHit:
    canonical: str
    tier: str                  # added | sugar_like | sweetener
    ingredient_line: str
    position: int              # 1-based position in the ingredient list
    percent: float | None      # declared percentage if the label gives one


def _match(patterns: list[str], text: str) -> bool:
    return any(re.search(p, text, flags=re.IGNORECASE) for p in patterns)


def classify_ingredient(line: str) -> tuple[str, str] | None:
    """Return (canonical, tier) when an ingredient line is a sugar, sugar-like or sweetener."""
    t = line.strip().lower()
    if not t:
        return None
    if _match(INTRINSIC, t) and not _match(_SUGAR_WORDS, t):
        return None
    for canon, pats in ADDED_SUGAR.items():
        if _match(pats, t):
            return canon, "added"
    for canon, pats in SWEETENER.items():
        if _match(pats, t):
            return canon, "sweetener"
    for canon, pats in SUGAR_LIKE.items():
        if _match(pats, t):
            return canon, "sugar_like"
    return None


def find_sugars(ingredients: list[dict]) -> list[SugarHit]:
    """ingredients: [{"name": str, "percent": float | None}, ...] in label order."""
    hits: list[SugarHit] = []
    pos = 0
    for ing in ingredients:
        if not ing.get("nested"):
            pos += 1                      # nested sub-ingredients inherit their parent's rank
        name = ing.get("name") or ""
        tint_or_taste = re.compile(r"flavou?r|colou?r", flags=re.IGNORECASE)
        if tint_or_taste.search(ing.get("parent") or "") or (len(name.split()) <= 3 and tint_or_taste.search(name)):
            continue                      # "Flavours (caramel, vanilla)", "caramel colour": a taste or a tint, not a sugar
        res = classify_ingredient(name)
        if res:
            canon, tier = res
            hits.append(SugarHit(canon, tier, name, max(pos, 1), ing.get("percent")))
    return hits


def consolidated_rank(ingredients: list[dict], hits: list[SugarHit]) -> dict:
    """
    Where would "all added sugars, combined" sit on the ingredient list?

    With declared percentages this is exact. Without them we lean on the one legal fact we
    have (descending order of weight): combined sugar weighs at least as much as the highest
    ranked sugar line, so its rank is <= that line. Two or more sugar lines inside the top five
    is called "likely top-2".
    """
    added = [h for h in hits if h.tier == "added"]
    if not added:
        return {"n_added_sugar_lines": 0, "best_single_rank": None,
                "combined_rank_estimate": None, "note": "no added-sugar ingredient lines"}
    best = min(h.position for h in added)
    pct_known = [h.percent for h in added if h.percent is not None]
    if pct_known and len(pct_known) == len(added):
        total = sum(pct_known)
        others = [ing.get("percent") for ing in ingredients
                  if ing.get("percent") is not None and classify_ingredient(ing.get("name") or "") is None]
        rank = 1 + sum(1 for p in others if p > total)
        return {"n_added_sugar_lines": len(added), "best_single_rank": best,
                "combined_rank_estimate": rank, "combined_percent": round(total, 1),
                "note": "computed from declared percentages"}
    in_top5 = sum(1 for h in added if h.position <= 5)
    if len(added) >= 2 and in_top5 >= 2:
        est, note = min(best, 2), (f"{len(added)} separate sugar lines, {in_top5} in the top 5: "
                                   "combined sugar is likely the #1 or #2 ingredient")
    elif len(added) >= 2:
        est, note = best, f"{len(added)} separate sugar lines; combined rank is at most #{best}"
    else:
        est, note = best, "single sugar line"
    return {"n_added_sugar_lines": len(added), "best_single_rank": best,
            "combined_rank_estimate": est, "note": note}
