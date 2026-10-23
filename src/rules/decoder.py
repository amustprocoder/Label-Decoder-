"""
The decoder: structured label in, honest label out.

Input (dict, produced by src/extract.py from a photo, or typed by hand):
{
  "product_name": str, "brand": str, "category": str, "barcode": str,
  "net_quantity_g": float, "serving_size_g": float, "servings_per_pack": float,
  "is_liquid": bool,
  "per_100": {"energy_kcal", "protein_g", "carbohydrate_g", "total_sugars_g", "added_sugars_g",
              "dietary_fibre_g", "total_fat_g", "saturated_fat_g", "trans_fat_g",
              "cholesterol_mg", "sodium_mg", "salt_g"},
  "ingredients": [{"name": str, "percent": float | None}, ...],   # label order
  "ingredients_text": str,
  "front_of_pack_claims": [str, ...],
  "as_prepared_note": str | None       # e.g. "values per 200 ml milk + 30 g powder"
}

Output: dict with sugar maths, claim checks, consolidated sugar rank, mislead flags, and a
one-line share text. Pure Python, no model call: the same input always gives the same verdict.
"""

from __future__ import annotations

import re
from dataclasses import asdict

from .fssai_claims import REG, check_schedule_claim, detect_claims
from .serving import (WHO_FREE_SUGAR_5PCT_G, FSSAI_RDA, per_serving, pct_energy_from, pct_of_rda,
                      pick_serving, sodium_from_salt, teaspoons)
from .sugar_aliases import POLYOL_LAXATIVE_NOTE, POLYOLS, consolidated_rank, find_sugars

INTRINSIC_SUGAR_SOURCES = [r"\bmilk\b", r"\bfruit\b", r"\bpulp\b", r"\bbanana\b", r"\bmango\b", r"\bapple\b",
                           r"\bgrape\b", r"\byogh?urt\b", r"\bcurd\b", r"\bdates?\b", r"\braisins?\b", r"\btomato\b"]
ANIMAL_SOURCES = [r"\bmilk\b", r"\bghee\b", r"\bbutter\b", r"\begg\b", r"\bcheese\b", r"\bcream\b", r"\bwhey\b",
                  r"\bcasein\b", r"\bmeat\b", r"\bchicken\b", r"\bfish\b", r"\bpaneer\b", r"\bcurd\b"]
ADDITIVE_MARKERS = [r"\bins\s*\d{3,4}\b", r"\b\d{3,4}\s*\(?[a-z]*\)?", r"\bflavou?r", r"\bpreservative", r"\bemulsifier",
                    r"\bstabili[sz]er", r"\bacidity\s*regulator", r"\bantioxidant", r"\bcolou?r\b", r"\bthickener",
                    r"\braising\s*agent", r"\bsweetener", r"\bhumectant", r"\bsequestrant"]
FREE_GLUTAMATE = [r"\byeast\s*extract\b", r"\bhydroly[sz]ed\s*(?:vegetable\s*)?protein\b", r"\bautoly[sz]ed\b",
                  r"\bsoy\s*sauce\b", r"\bdisodium\s*(?:inosinate|guanylate)\b", r"\b62[7-9]\b", r"\b63[0-5]\b"]
WHOLE_GRAIN_WORDS = [r"\bwhole\s*wheat\b", r"\batta\b", r"\bwhole\s*grain", r"\boats?\b", r"\bragi\b", r"\bjowar\b",
                     r"\bbajra\b", r"\bmillet", r"\bbrown\s*rice\b", r"\bquinoa\b"]


def _any(patterns: list[str], text: str) -> bool:
    return any(re.search(p, text, flags=re.IGNORECASE) for p in patterns)


def _num(x) -> float | None:
    try:
        return None if x is None or x == "" else float(x)
    except (TypeError, ValueError):
        return None


def _flag(code: str, severity: str, title: str, detail: str, rule_ref: str = REG) -> dict:
    return {"code": code, "severity": severity, "title": title, "detail": detail, "rule_ref": rule_ref}


def decode_label(label: dict) -> dict:
    per100 = {k: _num(v) for k, v in (label.get("per_100") or {}).items()}
    if per100.get("sodium_mg") is None and per100.get("salt_g") is not None:
        per100["sodium_mg"] = sodium_from_salt(per100["salt_g"])
    is_liquid = bool(label.get("is_liquid"))
    cat_text = f"{label.get('category') or ''} {label.get('product_name') or ''}".lower()
    if is_liquid and re.search(r"powder|malt|horlicks|bournvita|boost|chocolate|candy|candies|bar\b|dates?|raisin|dried|"
                               r"biscuit|cookie|mix\b|cereal|granola|gummies|syrup|balls?\b", cat_text):
        is_liquid = False                     # a malt powder or a chocolate tagged "beverage" by a crowd database
    if is_liquid and not re.search(r"beverage|drink|juice|\bmilk\b|water|soda|cola|sprite|mirinda|lassi|buttermilk|chaas|"
                                   r"\btea\b|coffee|nectar|squash|shake|smoothie|\boils?\b", cat_text):
        is_liquid = False                     # crowd data marks noodles, bread and oats "per 100 ml"; nothing says liquid
    if is_liquid and re.search(r"bread|\bbuns?\b|\bpav\b|noodle|pasta|\boats\b|chips|wafer|\bcurd\b|\bdahi\b", cat_text):
        is_liquid = False                     # "milk bread", "milk chocolate wafer": solids that mention milk
    unit = "ml" if is_liquid else "g"
    serving_g, serving_src = pick_serving(label)
    ingredients = label.get("ingredients") or []
    if not ingredients and label.get("ingredients_text"):
        ingredients = split_ingredients(label["ingredients_text"])
    ing_text = " ; ".join(i.get("name", "") for i in ingredients).lower()
    claims_raw = label.get("front_of_pack_claims") or []

    # ---- sugar maths -------------------------------------------------------------------
    total_100 = per100.get("total_sugars_g")
    added_100 = per100.get("added_sugars_g")
    hits = find_sugars(ingredients)
    added_lines = [h for h in hits if h.tier == "added"]
    sweetener_lines = [h for h in hits if h.tier == "sweetener"]
    sugar_like_lines = [h for h in hits if h.tier == "sugar_like"]
    rank = consolidated_rank(ingredients, hits)
    has_intrinsic = _any(INTRINSIC_SUGAR_SOURCES, ing_text)

    intrinsic_est = _intrinsic_sugar_estimate(ingredients)
    if added_100 is not None:
        added_est, added_method = added_100, "declared on pack"
    elif total_100 is not None and added_lines and not has_intrinsic:
        added_est, added_method = total_100, "estimated = total sugars (no milk or fruit in the list, so all sugar is added)"
    elif total_100 is not None and added_lines and has_intrinsic and intrinsic_est is not None:
        added_est = max(0.0, total_100 - intrinsic_est["g"])
        added_method = (f"estimated = total sugars minus about {intrinsic_est['g']:.1f} g natural sugar from "
                        f"{intrinsic_est['from']} (declared %)")
    elif total_100 is not None and added_lines and has_intrinsic:
        added_est, added_method = None, "cannot separate added from milk or fruit sugar; pack declares neither added sugar nor ingredient percentages"
    elif total_100 is not None and not added_lines:
        added_est, added_method = 0.0, "no added-sugar ingredient found; all sugar is intrinsic"
    else:
        added_est, added_method = None, "total sugars not declared"

    total_serve = per_serving(total_100, serving_g)
    added_serve = per_serving(added_est, serving_g)
    sugar = {
        "total_sugars_per_100": total_100,
        "sugar_pct_by_weight": total_100 if not is_liquid else None,
        "sugar_g_per_100ml": total_100 if is_liquid else None,
        "added_sugars_per_100": added_est,
        "added_sugar_method": added_method,
        "serving_g": serving_g,
        "serving_source": serving_src,
        "total_sugars_per_serve": total_serve,
        "teaspoons_total_per_serve": teaspoons(total_serve),
        "added_sugars_per_serve": added_serve,
        "teaspoons_added_per_serve": teaspoons(added_serve),
        "pct_of_who_25g_per_serve": (100.0 * added_serve / WHO_FREE_SUGAR_5PCT_G) if added_serve is not None else None,
        "pct_of_fssai_50g_per_serve": pct_of_rda(added_serve, "added_sugars_g"),
        "pct_energy_from_sugar": pct_energy_from(total_100, per100.get("energy_kcal"), "total_sugars_g"),
    }

    # ---- claims -------------------------------------------------------------------------
    detected = detect_claims(claims_raw)
    checks = []
    soft_types = set()
    for raw, ctype, kind in detected:
        if kind == "schedule":
            checks.append(asdict(check_schedule_claim(raw, ctype, per100, serving_g, is_liquid, per100.get("energy_kcal"))))
        else:
            soft_types.add(ctype)
    claim_types = {c["claim_type"] for c in checks}

    # ---- mislead flags ------------------------------------------------------------------
    flags: list[dict] = []

    if rank["n_added_sugar_lines"] >= 2:
        names = ", ".join(sorted({h.canonical for h in added_lines}))
        flags.append(_flag("SUGAR_SPLIT", "high", f"Sugar listed under {rank['n_added_sugar_lines']} different names",
                           f"{names}. {rank['note']}. Legally fine (ingredients only need descending order of weight); "
                           f"practically it keeps 'sugar' off the top of the list.",
                           "FSS (Labelling & Display) Regs 2020, Reg 5(2): ingredients in descending order of weight"))

    if "no added sugar" in claim_types:
        substitutes = [h for h in added_lines]
        if substitutes:
            names = ", ".join(sorted({h.canonical for h in substitutes}))
            flags.append(_flag("NAS_SUBSTITUTE", "high", "'No added sugar' with sugar-substituting ingredients",
                               f"Ingredient list contains: {names}. Reg 8 allows the claim only when no sugars and no "
                               f"sugar-substituting ingredients (concentrated fruit juice, dried fruit paste, honey, "
                               f"jaggery, malt) have been added. This claim is not supported by the label.",
                               f"{REG}, Reg 8 (non-addition claims)"))
        elif total_serve is not None and total_serve >= 10:
            flags.append(_flag("NAS_HIGH_INTRINSIC", "medium", "'No added sugar' but one serve still has "
                               f"{total_serve:.0f} g sugar ({teaspoons(total_serve):.1f} tsp)",
                               "The claim is true: the sugar comes from fruit or milk. Metabolically, juice sugar is "
                               "free sugar under the WHO definition; the body does not read the label.",
                               "WHO 2015 free-sugars guideline"))

    if "sugar free" in claim_types or "low sugar" in claim_types:
        polyols = [h for h in sweetener_lines if h.canonical in POLYOLS]
        if polyols:
            flags.append(_flag("SUGAR_FREE_POLYOL", "medium", "Sugar free, built on polyols",
                               ", ".join(sorted({h.canonical for h in polyols})) + f". {POLYOL_LAXATIVE_NOTE} "
                               "Polyols still carry 2 to 3 kcal/g; 'sugar free' is not 'carb free'.",
                               "FSS (Food Products Standards & Food Additives) Regs 2011"))
        if sweetener_lines and not polyols:
            flags.append(_flag("SUGAR_FREE_SWEETENER", "low", "Sweetness comes from non-nutritive sweeteners",
                               ", ".join(sorted({h.canonical for h in sweetener_lines})) +
                               ". Label must carry 'contains artificial sweetener' and the not-for-children advisory.",
                               "FSS (Labelling & Display) Regs 2020, Reg 10"))
        if sugar_like_lines:
            flags.append(_flag("SUGAR_FREE_MALTODEXTRIN", "medium", "Sugar free, but carries high-GI carbohydrate",
                               ", ".join(sorted({h.canonical for h in sugar_like_lines})) +
                               ". Maltodextrin is not a 'sugar' under the regulation, yet its glycaemic index is above table sugar.",
                               "FSSAI Schedule I defines 'sugars' as mono- and disaccharides only"))

    for c in checks:
        if c["verdict"] == "legal but misleading":
            flags.append(_flag("PER100_VS_SERVE", "high", f"'{c['claim_text']}' holds per 100 {unit}, not per serve",
                               c["explanation"], c["rule_ref"]))
        elif c["verdict"] == "fails":
            flags.append(_flag("CLAIM_FAILS", "high", f"'{c['claim_text']}' does not meet the Schedule I test",
                               c["explanation"], c["rule_ref"]))

    sugar_top = rank["combined_rank_estimate"] is not None and rank["combined_rank_estimate"] <= 2
    halo = soft_types & {"healthy", "energy / growth", "immunity", "real fruit", "natural"}
    if sugar_top and halo:
        flags.append(_flag("HALO_OVER_SUGAR", "high", "Health language on a pack where sugar is a top-2 ingredient",
                           f"Front says {', '.join(sorted(halo))}; the combined sugar lines rank #{rank['combined_rank_estimate']}. "
                           f"Reg 4 says claims must not encourage excess consumption or mislead on nutritional value.",
                           f"{REG}, Reg 4"))
    if total_100 is not None and total_100 >= 20 and "healthy" in soft_types and not sugar_top:
        flags.append(_flag("HEALTH_DRINK_SUGAR", "high", f"Marketed as healthy, {total_100:g}% sugar by weight",
                           f"Every 100 {unit} carries {total_100:g} g sugar, {teaspoons(total_100):.0f} teaspoons.", f"{REG}, Reg 4"))

    if "immunity" in soft_types:
        flags.append(_flag("IMMUNITY_CLAIM", "medium", "Immunity claim",
                           "Health and disease-risk-reduction claims need scientific substantiation and FSSAI approval "
                           "(Reg 6, Schedule III/IV). 'Immunity' on a pack is marketing unless the approved wording is used.",
                           f"{REG}, Reg 6"))
    if "energy / growth" in soft_types:
        flags.append(_flag("ENERGY_GROWTH_CLAIM", "low", "Energy, growth or strength language",
                           "Energy on a label legally means calories. Growth, stamina and brain claims are health claims "
                           "and need approval; 'energy' is a nutrient claim only if it says kcal.", f"{REG}, Reg 6-7"))

    if "natural" in soft_types and _any(ADDITIVE_MARKERS, ing_text):
        flags.append(_flag("NATURAL_WITH_ADDITIVES", "high", "'Natural' with additives in the list",
                           "Reg 5: 'natural' is allowed only for a single food, minimally processed, with no additives, "
                           "flavours or preservatives. Composite foods may at most say 'made from natural ingredients'.",
                           f"{REG}, Reg 5"))
    if "real fruit" in soft_types:
        fruit_pct = [i.get("percent") for i in ingredients if i.get("percent") is not None and
                     _any([r"fruit", r"juice", r"pulp", r"mango", r"apple", r"orange", r"grape", r"berry", r"banana"], i.get("name", ""))]
        if fruit_pct and max(fruit_pct) < 10:
            flags.append(_flag("REAL_FRUIT_TRACE", "high", f"'Real fruit' at {max(fruit_pct):g}%",
                               "The emphasised ingredient is a trace. The pack must declare its percentage (QUID) and it has; "
                               "the front-of-pack art does the rest.", "FSS (Labelling & Display) Regs 2020, Reg 5(3)"))
        elif not fruit_pct:
            flags.append(_flag("REAL_FRUIT_NO_PCT", "medium", "'Real fruit' without a percentage",
                               "When an ingredient is emphasised on the pack, its quantity must be declared. None found.",
                               "FSS (Labelling & Display) Regs 2020, Reg 5(3)"))
    if ("multigrain" in soft_types or "whole grain" in soft_types) and ingredients:
        first = ingredients[0].get("name", "").lower()
        if _any([r"refined\s*wheat\s*flour", r"\bmaida\b", r"\bwheat\s*flour\b(?!.*(?:whole|atta))"], first):
            flags.append(_flag("MULTIGRAIN_MAIDA", "high", "Multigrain or whole grain, but maida is ingredient #1",
                               f"First ingredient: '{ingredients[0].get('name')}'. The grains are garnish.", f"{REG}, Reg 4"))
    if "baked" in soft_types and per100.get("total_fat_g") is not None and per100["total_fat_g"] >= 20:
        flags.append(_flag("BAKED_STILL_FATTY", "medium", f"Baked, and still {per100['total_fat_g']:g} g fat per 100 g",
                           "Baked is a process claim, not a nutrition claim. Fried chips sit around 30 g/100 g.", f"{REG}, Reg 4"))
    if "cholesterol free" in claim_types and ing_text and not _any(ANIMAL_SOURCES, ing_text):
        flags.append(_flag("CHOLESTEROL_FREE_PLANT", "medium", "'Cholesterol free' on a plant-based food",
                           "No plant food contains cholesterol. Reg 4 prohibits claims implying a special property "
                           "that every food of the same type has.", f"{REG}, Reg 4"))
    if "no msg" in soft_types and _any(FREE_GLUTAMATE, ing_text):
        flags.append(_flag("NO_MSG_GLUTAMATE", "medium", "'No MSG' with free-glutamate ingredients",
                           "Yeast extract, hydrolysed protein, INS 627/631 deliver the same glutamate. No MSG added; MSG effect kept.",
                           f"{REG}, Reg 4"))
    if label.get("as_prepared_note"):
        flags.append(_flag("AS_PREPARED", "medium", "Nutrition declared 'as prepared'",
                           f"'{label['as_prepared_note']}'. Protein and calcium on the pack include the milk you add; "
                           "the powder alone is mostly sugar and malt. Compare per 100 g of powder.",
                           "FSS (Labelling & Display) Regs 2020, Reg 5(4)"))

    if serving_g is not None and label.get("serving_size_g"):
        tiny = (not is_liquid and serving_g < 15) or (is_liquid and serving_g < 100)
        if tiny:
            flags.append(_flag("SERVING_TINY", "medium", f"Declared serve is {serving_g:g} {unit}",
                               "A serve this small makes every per-serve number look harmless. Ask whether anyone stops there.",
                               "FSS (Labelling & Display) Regs 2020 do not prescribe serve sizes"))
    if added_serve is not None:
        if added_serve >= WHO_FREE_SUGAR_5PCT_G:
            flags.append(_flag("WHO_LIMIT_BLOWN", "high", f"One serve = {100 * added_serve / WHO_FREE_SUGAR_5PCT_G:.0f}% of the WHO 25 g/day free-sugar limit",
                               f"{added_serve:.1f} g added sugar, {teaspoons(added_serve):.1f} teaspoons, in {serving_g:g} {unit}.",
                               "WHO 2015 free-sugars guideline (conditional 5% of energy)"))
        elif added_serve >= WHO_FREE_SUGAR_5PCT_G / 2:
            flags.append(_flag("WHO_LIMIT_HALF", "medium", f"One serve = {100 * added_serve / WHO_FREE_SUGAR_5PCT_G:.0f}% of the WHO 25 g/day limit",
                               f"{added_serve:.1f} g added sugar, {teaspoons(added_serve):.1f} teaspoons.", "WHO 2015"))
    sod_serve = per_serving(per100.get("sodium_mg"), serving_g)
    if sod_serve is not None and sod_serve >= 0.2 * FSSAI_RDA["sodium_mg"]:
        flags.append(_flag("SODIUM_HIGH", "medium", f"One serve = {pct_of_rda(sod_serve, 'sodium_mg'):.0f}% of daily sodium",
                           f"{sod_serve:.0f} mg sodium per {serving_g:g} {unit}.", "FSS (Labelling & Display) Regs 2020 RDA"))
    sat = per100.get("saturated_fat_g")
    if sat is not None and per100.get("energy_kcal"):
        share = pct_energy_from(sat, per100["energy_kcal"], "total_fat_g")
        if share and share >= 20:
            flags.append(_flag("SAT_FAT_HIGH", "low", f"{share:.0f}% of energy from saturated fat",
                               f"{sat:g} g saturated fat per 100 {unit}.", "WHO: keep saturated fat under 10% of energy"))
    tf = per100.get("trans_fat_g")
    if tf is not None and tf > 0.2 and "trans fat free" not in claim_types:
        flags.append(_flag("TRANS_FAT", "medium", f"{tf:g} g trans fat per 100 {unit}",
                           "India caps industrial trans fat at 2% of total fat (2022). Anything above 0.2 g/100 g cannot be called trans-fat free.",
                           "FSS (Prohibition & Restrictions on Sales) 2nd Amendment 2021"))

    sev_order = {"high": 0, "medium": 1, "low": 2}
    flags.sort(key=lambda f: sev_order[f["severity"]])

    # ---- summary lines ------------------------------------------------------------------
    name = label.get("product_name") or "This product"
    parts = []
    if total_100 is not None:
        parts.append(f"{total_100:g}% sugar by weight" if not is_liquid else f"{total_100:g} g sugar per 100 ml")
    if total_serve is not None:
        parts.append(f"{teaspoons(total_serve):.1f} tsp sugar per {serving_g:g} {unit} serve")
    if rank["n_added_sugar_lines"] >= 2:
        parts.append(f"sugar under {rank['n_added_sugar_lines']} names, combined rank #{rank['combined_rank_estimate']}")
    misleading = [c for c in checks if c["verdict"] in ("legal but misleading", "fails")]
    if misleading:
        parts.append(f"'{misleading[0]['claim_text']}' " + ("fails" if misleading[0]["verdict"] == "fails" else "only holds per 100 g"))
    share_line = f"{name}: " + "; ".join(parts) + "." if parts else f"{name}: not enough label data to decode."

    honest = []
    if total_serve is not None:
        honest.append(f"One serve ({serving_g:g} {unit}, {serving_src}) carries {total_serve:.1f} g sugar = {teaspoons(total_serve):.1f} teaspoons.")
    if added_serve is not None and added_est != total_100:
        honest.append(f"Of that, about {added_serve:.1f} g is added ({added_method}).")
    elif added_est is not None and added_lines:
        honest.append(f"All of it is added sugar ({added_method}).")
    for c in checks:
        honest.append(f"Claim '{c['claim_text']}': {c['verdict']}. {c['explanation']}")
    for f in flags[:3]:
        honest.append(f"{f['title']}: {f['detail']}")

    return {
        "product": {"name": label.get("product_name"), "brand": label.get("brand"), "category": label.get("category"),
                    "barcode": label.get("barcode"), "is_liquid": is_liquid},
        "serving": {"g": serving_g, "source": serving_src},
        "sugar": sugar,
        "sugar_lines": [asdict(h) for h in hits],
        "consolidated_sugar": rank,
        "claims": checks,
        "soft_claims": sorted(soft_types),
        "flags": flags,
        "honest_label": " ".join(honest),
        "share_line": share_line,
        "severity_score": sum({"high": 3, "medium": 2, "low": 1}[f["severity"]] for f in flags),
    }


INTRINSIC_SUGAR_FRACTION = [          # (pattern, grams of natural sugar per gram of ingredient)
    (r"\bmilk\s*solids?\b|\bskimmed?\s*milk\s*powder\b|\bwhole\s*milk\s*powder\b|\bsmp\b|\bwmp\b", 0.50),
    (r"\bwhey\s*(?:powder|solids)\b", 0.70),
    (r"^(?:toned|double\s*toned|full\s*cream|skimmed|standardised)?\s*milk$", 0.05),
    (r"\bdates?\b|\braisins?\b|\bdried\s*fruit", 0.65),
    (r"\bfruit\s*pulp\b|\bmango\s*pulp\b|\bfruit\s*juice\b|\bbanana\b|\bapple\b|\bmango\b|\bgrape\b", 0.10),
    (r"\btomato\b", 0.03),
]


def _intrinsic_sugar_estimate(ingredients: list[dict]) -> dict | None:
    """Natural sugar (g per 100 g product) from milk or fruit ingredients that declare a percentage."""
    total, names = 0.0, []
    for ing in ingredients:
        pct = ing.get("percent")
        if pct is None:
            continue
        name = (ing.get("name") or "").lower()
        for pat, frac in INTRINSIC_SUGAR_FRACTION:
            if re.search(pat, name, flags=re.IGNORECASE):
                total += pct * frac
                names.append(ing.get("name"))
                break
    return {"g": total, "from": ", ".join(names)} if names else None


def split_ingredients(text: str) -> list[dict]:
    """
    Turn a raw ingredient string into [{"name", "percent"}] in label order.
    Handles nested brackets by keeping the outer item and the bracketed sub-items as separate lines
    (the sub-items matter for sugar aliases: "Choco chips (sugar, cocoa, ...)").
    """
    text = re.sub(r"^\s*ingredients?\s*[:\-]\s*", "", text or "", flags=re.IGNORECASE)
    text = text.replace("[", "(").replace("]", ")").replace("{", "(").replace("}", ")")
    items: list[dict] = []
    for piece in _split_top_level(text):
        _emit(piece, items, nested=False)
    return items


def _split_top_level(text: str) -> list[str]:
    depth, buf, pieces = 0, "", []
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        if ch in ",;" and depth == 0:
            pieces.append(buf)
            buf = ""
        else:
            buf += ch
    pieces.append(buf)
    return [p.strip(" .\n\t") for p in pieces if p.strip(" .\n\t")]


def _emit(piece: str, items: list[dict], nested: bool, parent: str | None = None) -> None:
    """Emit one ingredient (name + declared %) then recurse into its bracketed sub-ingredients."""
    # split "name (sub, sub (subsub)) 8%" into name / bracket content
    name_part, inner_parts = "", []
    depth, buf = 0, ""
    for ch in piece:
        if ch == "(":
            if depth == 0:
                name_part += buf
                buf = ""
            else:
                buf += ch
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                inner_parts.append(buf)
                buf = ""
            else:
                buf += ch
        else:
            buf += ch
    name_part += buf
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", name_part)
    pct = float(m.group(1)) if m else None
    if pct is None:   # "% inside the bracket": Choco chips (8%)
        for ip in inner_parts:
            m2 = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*%\s*", ip)
            if m2:
                pct = float(m2.group(1))
    name = re.sub(r"\d+(?:\.\d+)?\s*%", "", name_part).strip(" :,-.")
    if name and not re.fullmatch(r"ins\s*\d+[a-z]?", name, flags=re.IGNORECASE):
        row = {"name": name, "percent": pct}
        if nested:
            row["nested"] = True
            row["parent"] = parent
        items.append(row)
    for ip in inner_parts:
        if re.fullmatch(r"\s*\d+(?:\.\d+)?\s*%\s*", ip):
            continue
        for sub in _split_top_level(ip):
            _emit(sub, items, nested=True, parent=name or parent)
