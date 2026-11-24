"""
The health check: four lights and one verdict. Pure Python, no model call.

    1. Sugar           free sugar per 100 g and per serve
    2. Fat and salt    saturated fat, trans fat, salt
    3. Ingredients     what the pack is made of and how processed it is
    4. Good stuff      protein and fibre

Every light is green, amber (shown as yellow) or red, from a published cut-off. No weights of our own:
the verdict only counts the lights.

    Healthy            no red, at most one yellow
    Okay, sometimes    one red, or two or more yellows
    Not healthy        two or more reds

Where the cut-offs come from
  - Per 100 g / 100 ml colours for sugar, saturated fat and salt: the UK front-of-pack traffic-light
    criteria (Department of Health / Food Standards Agency guidance, 2016). India has no colour scheme in
    force yet, and these are the same cut-offs the traffic-light card in this app already uses.
  - "One serve is red on its own": the same UK guidance turns a nutrient red when one portion carries
    30% of the day's reference amount (27 g of 90 g sugars, 6 g of 20 g saturates, 1.8 g of 6 g salt).
    The 30% share is kept; the day's amounts are the ones used in India: 25 g free sugar (WHO), 22 g
    saturated fat and 2000 mg sodium (FSSAI Labelling and Display Regulations 2020).
  - Trans fat: 0.2 g per 100 g is the most a pack may hold and still call itself trans fat free
    (FSS Advertising and Claims Regulations 2018, Schedule I).
  - Ingredients: the NOVA markers of ultra-processed food (Monteiro et al., Public Health Nutrition 2019):
    substances no home kitchen uses, and additives that only change colour, taste or texture.
    Preservatives, antioxidants, acidity regulators and raising agents are not counted, because NOVA
    allows them in ordinary processed food. Refined flour and palm oil are named separately; the
    ICMR-NIN Dietary Guidelines for Indians (2024) ask people to limit both.
  - Good stuff: "source of" and "high in" protein and fibre exactly as FSSAI Schedule I defines them.

Not medical advice: the check knows the pack, not the person eating it.
"""

from __future__ import annotations

import math
import re

from .serving import FSSAI_RDA, TEASPOON_G, WHO_FREE_SUGAR_5PCT_G, per_serving

# (green up to and including, red above), per 100 g of food or 100 ml of drink
FSA_FOOD = {"sugar": (5.0, 22.5), "satfat": (1.5, 5.0), "salt": (0.3, 1.5)}
FSA_DRINK = {"sugar": (2.5, 11.25), "satfat": (0.75, 2.5), "salt": (0.3, 0.75)}
SERVE_RED_PCT = 30.0          # one serve carrying this share of a day's limit is red on its own
TRANS_FAT_FREE_G = 0.2        # per 100 g; above this a pack cannot claim "trans fat free"
ENERGY_FREE_KCAL = 4.0        # per 100 ml; FSSAI Schedule I "energy free"
COOKING_FAT = r"\boils?\b|\bghee\b|\bvanaspati\b"
DAY = {"sugar": WHO_FREE_SUGAR_5PCT_G, "satfat": FSSAI_RDA["saturated_fat_g"], "sodium": FSSAI_RDA["sodium_mg"]}

# FSSAI Schedule I: protein as % of the 54 g RDA, fibre in g, per 100 g (solid) or per 100 ml (liquid)
PROTEIN_PCT = {"solid": (10.0, 20.0), "liquid": (5.0, 10.0)}      # (source of, high in)
FIBRE_G = {"solid": (3.0, 6.0), "liquid": (1.5, 3.0)}

ORDER = {"grey": 0, "green": 1, "amber": 2, "red": 3}

DAIRY = r"\bmilk\b|\bcurd\b|\bdahi\b|\byogh?urt\b|\blassi\b|\bbuttermilk\b|\bchaas\b|\bpaneer\b|\bghee\b|\bbutter\b|\bcream\b"
ALL_FREE_SUGAR = r"\bhoney|\bsyrups?\b|\bjaggery\b|\bgur\b|\bjams?\b"      # WHO counts all of their sugar as free
REFINED_FLOUR = r"\bmaida\b|\brefined\s+(?:wheat\s+)?flour\b|\ball[\s-]*purpose\s+flour\b|\bwhite\s+flour\b"
SUGAR_FIRST = r"^\s*(?:sugar|sucrose|jaggery|glucose|liquid\s+glucose|invert\s+(?:sugar|syrup))\b"
INDUSTRIAL_FAT = r"\bhydrogenated\b|\bvanaspati\b|\binteresterified\b|\bmargarine\b|\bshortening\b"
PALM = r"\bpalm(?:olein)?\b"
# food substances that kitchens do not use (NOVA group 4 markers)
INDUSTRIAL = [
    (r"\bmaltodextrin\b", "maltodextrin"),
    (r"\binvert\s+(?:sugar|syrup)\b", "invert syrup"),
    (r"\b(?:liquid\s+glucose|glucose\s+syrup|corn\s+syrup|fructose\s+syrup|glucose[\s-]*fructose)\b", "glucose syrup"),
    (r"\bdextrose\b", "dextrose"),
    (r"\bhydroly[sz]ed\b", "hydrolysed protein"),
    (r"\bmodified\s+starch\b|\bstarch\s*\(?(?:ins\s*)?14\d\d", "modified starch"),
    (r"\bprotein\s+isolate\b|\bisolated\s+\w+\s+protein\b", "protein isolate"),
]
# additives that only change colour, taste or texture (NOVA "cosmetic" additive classes)
COSMETIC = [
    (r"\bflavou?r\s*enhancers?\b", "flavour enhancer"),
    (r"\bcolou?rs?\b|\bcolou?ring\b", "colour"),
    (r"\bflavou?r(?:s|ing|ings)?\b(?!\s*enhancer)", "added flavour"),
    (r"\bemulsif", "emulsifier"),
    (r"\bsweeteners?\b", "sweetener"),
    (r"\bthickeners?\b|\bstabili[sz]ers?\b|\bgelling\b", "thickener"),
    (r"\bglazing\b|\banti[\s-]*foaming\b|\bbulking\b", "texture agent"),
]
HI = {"maltodextrin": "माल्टोडेक्सट्रिन", "invert syrup": "इनवर्ट सिरप", "glucose syrup": "ग्लूकोज़ सिरप",
      "dextrose": "डेक्सट्रोज़", "hydrolysed protein": "हाइड्रोलाइज़्ड प्रोटीन", "modified starch": "मॉडिफ़ाइड स्टार्च",
      "protein isolate": "प्रोटीन आइसोलेट", "flavour enhancer": "स्वाद बढ़ाने वाला", "colour": "रंग",
      "added flavour": "फ़्लेवर", "emulsifier": "इमल्सिफ़ायर", "sweetener": "स्वीटनर", "thickener": "गाढ़ा करने वाला",
      "texture agent": "टेक्सचर एजेंट"}


def _light(value: float | None, cut: tuple[float, float]) -> str:
    if value is None:
        return "grey"
    return "green" if value <= cut[0] else ("red" if value > cut[1] else "amber")


def _worst(*colors: str) -> str:
    return max(colors, key=lambda c: ORDER[c])


def _pct(value: float | None, day: float) -> float | None:
    return None if value is None else 100.0 * value / day


def _n(v: float) -> str:
    return f"{v:.1f}".rstrip("0").rstrip(".")


# ---------------------------------------------------------------------------------------------
def _check(key: str, color: str, head: tuple[str, str], points: list[tuple[str, str]], **extra) -> dict:
    """One light: a short headline and the reasons as separate points, in English and Hindi."""
    line = head[0] + "." + "".join(f" {p[0]}." for p in points)
    line_hi = head[1] + "।" + "".join(f" {p[1]}।" for p in points)
    return {"key": key, "color": color, "head": head[0], "head_hi": head[1], "points": [list(p) for p in points],
            "line": line, "line_hi": line_hi, **extra}


def _join(words: list[str], joiner: str) -> str:
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + joiner + words[-1]


def _sugar(per100: dict, sugar: dict, serving_g: float | None, is_liquid: bool, ing_text: str,
           cat_text: str, n_names: int) -> dict:
    total = per100.get("total_sugars_g")
    added = sugar.get("added_sugars_per_100")
    dairy = bool(re.search(DAIRY, f"{cat_text} ; {ing_text}", flags=re.IGNORECASE))
    # WHO limits "free" sugar: added sugar plus the sugar in juice, not the sugar inside milk or whole fruit.
    # So the added figure is used when the pack or its ingredient list gives one; a drink that is not dairy
    # counts in full (juice sugar is free sugar); with no ingredient list there is nothing to subtract.
    if total is None:
        free, basis = added, "added"
    elif (added is None or not ing_text.strip() or (is_liquid and not dairy)
          or re.search(ALL_FREE_SUGAR, cat_text, flags=re.IGNORECASE)):
        free, basis = total, "total"
    else:
        free, basis = min(added, total), "added"
    if free is None:
        return _check("sugar", "grey", ("Not printed on the pack", "पैकेट पर नहीं लिखी"), [],
                      pct_day=None, basis=None, per_100=None)
    serve = per_serving(free, serving_g)
    pct = _pct(serve, DAY["sugar"])
    color = _light(free, (FSA_DRINK if is_liquid else FSA_FOOD)["sugar"])
    if pct is not None and pct >= SERVE_RED_PCT:
        color = "red"
    if n_names >= 2:
        color = _worst(color, "amber")           # sugar split across names is never a clean green
    unit = "ml" if is_liquid else "g"
    shown = total if total is not None else free            # the spoons match the banner: all the sugar in a serve
    shown_serve = per_serving(shown, serving_g)
    points: list[tuple[str, str]] = []
    if shown_serve is not None and shown_serve >= 1.0:
        tsp = shown_serve / TEASPOON_G
        head = (f"{tsp:.1f} spoons in one serve", f"एक सर्व में {tsp:.1f} चम्मच")
        if free < 0.5:
            points.append(("None of it is added sugar", "ऊपर से डाली गई चीनी बिल्कुल नहीं"))
        elif basis == "total" or shown - free < 0.5:
            points.append((f"{pct:.0f}% of a day's limit", f"दिन की सीमा का {pct:.0f}%"))
        else:
            points.append((f"The added part is {pct:.0f}% of a day's limit", f"ऊपर से डाली गई चीनी दिन की सीमा का {pct:.0f}%"))
        points.append((f"{_n(shown)} g in every 100 {unit}", f"हर 100 {unit} में {_n(shown)} ग्राम"))
    elif shown < 0.5:
        head = ("Almost no sugar", "लगभग कोई चीनी नहीं")
    else:
        head = (f"{_n(shown)} g in every 100 {unit}", f"हर 100 {unit} में {_n(shown)} ग्राम")
    if n_names >= 2:
        points.append((f"Listed under {n_names} different names", f"{n_names} अलग नामों से लिखी है"))
    return _check("sugar", color, head, points, pct_day=pct, basis=basis, per_100=free)


def _fat_salt(per100: dict, serving_g: float | None, is_liquid: bool, ing_text: str = "", cat_text: str = "") -> dict:
    cuts = FSA_DRINK if is_liquid else FSA_FOOD
    sat, trans, sodium = per100.get("saturated_fat_g"), per100.get("trans_fat_g"), per100.get("sodium_mg")
    salt = per100.get("salt_g")
    if salt is None and sodium is not None:
        salt = sodium * 2.5 / 1000.0
    if sodium is None and salt is not None:
        sodium = salt * 1000.0 / 2.5
    sat_pct = _pct(per_serving(sat, serving_g), DAY["satfat"])
    salt_pct = _pct(per_serving(sodium, serving_g), DAY["sodium"])
    sat_c = "red" if (sat_pct or 0) >= SERVE_RED_PCT else _light(sat, cuts["satfat"])
    salt_c = "red" if (salt_pct or 0) >= SERVE_RED_PCT else _light(salt, cuts["salt"])
    # milk fat carries a little natural trans fat; the limit is about the industrial kind (hydrogenated fat)
    natural = (re.search(DAIRY, f"{cat_text} ; {ing_text}", flags=re.IGNORECASE)
               and not re.search(INDUSTRIAL_FAT, ing_text, flags=re.IGNORECASE))
    trans_c = "grey" if trans is None else ("red" if trans > TRANS_FAT_FREE_G and not natural else "green")
    color = _worst(sat_c, salt_c, trans_c if trans_c == "red" else "grey")
    extra = {"satfat_pct_day": sat_pct, "sodium_pct_day": salt_pct, "satfat_color": sat_c, "salt_color": salt_c,
             "trans_color": trans_c}
    if sat is None and salt is None and trans is None:
        return _check("fat_salt", "grey", ("Not printed on the pack", "पैकेट पर नहीं लिखा"), [], **extra)
    word = {"red": "high", "amber": "medium", "green": "low"}
    word_hi = {"red": "ज़्यादा", "amber": "मध्यम", "green": "कम"}
    parts = [("saturated fat", "सैचुरेटेड फ़ैट", sat_c, sat_pct), ("salt", "नमक", salt_c, salt_pct)]
    parts = [p for p in parts if p[2] != "grey"]
    points: list[tuple[str, str]] = []
    for name, name_hi, c, pct in parts:
        tail = f", {pct:.0f}% of a day in one serve" if pct is not None and pct >= 1 else ""
        tail_hi = f", एक सर्व में दिन का {pct:.0f}%" if pct is not None and pct >= 1 else ""
        points.append((f"{name.capitalize()}: {word[c]}{tail}", f"{name_hi}: {word_hi[c]}{tail_hi}"))
    if trans_c == "red":
        points.append((f"Trans fat: {_n(trans)} g in 100 g, the worst kind of fat", f"ट्रांस फ़ैट: 100 ग्राम में {_n(trans)} ग्राम, सबसे ख़राब फ़ैट"))
    lead = "red" if any(p[2] == "red" for p in parts) or trans_c == "red" else ("amber" if any(p[2] == "amber" for p in parts) else "green")
    names = [p[0] for p in parts if p[2] == lead] + (["trans fat"] if trans_c == "red" else [])
    names_hi = [p[1] for p in parts if p[2] == lead] + (["ट्रांस फ़ैट"] if trans_c == "red" else [])
    if not names:                                           # only a clean trans-fat figure was printed
        return _check("fat_salt", color, ("No trans fat", "ट्रांस फ़ैट नहीं"), points, **extra)
    start = {"red": "High in", "amber": "Medium on", "green": "Low in"}[lead]
    head = (f"{start} {_join(names, ' and ')}", f"{_join(names_hi, ' और ')} {word_hi[lead]}")
    return _check("fat_salt", color, head, points, **extra)


def ingredient_markers(ingredients: list[dict]) -> list[tuple[str, str, str]]:
    """What in the ingredient list counts against the pack: (code, English, Hindi), one entry per marker."""
    items = [i for i in ingredients if (i.get("name") or "").strip()]
    names = [i["name"].lower() for i in items]
    top = [n for n, i in zip(names, items) if not i.get("nested")]
    text = " ; ".join(names)
    first3, seen_top = [], 0                    # the first three ingredients, each with what its brackets hold
    for n, i in zip(names, items):
        seen_top += 0 if i.get("nested") else 1
        if seen_top <= 3:
            first3.append(n)
    out: list[tuple[str, str, str]] = []
    if top and re.search(REFINED_FLOUR, top[0]):
        out.append(("refined_flour_first", "mostly maida (refined flour)", "सबसे ज़्यादा मैदा"))
    elif top and re.search(SUGAR_FIRST, top[0]):
        out.append(("sugar_first", "sugar is the first ingredient", "सबसे ज़्यादा चीनी"))
    if re.search(INDUSTRIAL_FAT, text):
        out.append(("industrial_fat", "hydrogenated fat", "हाइड्रोजनेटेड फ़ैट"))
    elif any(re.search(PALM, n) for n in first3):
        out.append(("palm_oil", "palm oil near the top", "पाम ऑयल ऊपर के पास"))
    for pat, name in INDUSTRIAL:
        if re.search(pat, text):
            out.append(("industrial:" + name, name, HI[name]))
    for pat, name in COSMETIC:
        if re.search(pat, text):
            out.append(("additive:" + name, name, HI[name]))
    return out


def ingredient_flag(text: str) -> str | None:
    """Why one ingredient (with whatever its brackets hold) counts against the pack, or None. For highlighting."""
    t = text.lower()
    if re.search(REFINED_FLOUR, t):
        return "refined flour"
    if re.search(INDUSTRIAL_FAT, t):
        return "hydrogenated fat"
    if re.search(PALM, t):
        return "palm oil"
    for pat, name in INDUSTRIAL + COSMETIC:
        if re.search(pat, t):
            return name
    return None


def _ingredients(ingredients: list[dict]) -> dict:
    if not [i for i in ingredients if (i.get("name") or "").strip()]:
        return _check("ingredients", "grey", ("The list was not read", "सूची नहीं पढ़ी जा सकी"), [], markers=[])
    marks = ingredient_markers(ingredients)
    color = "green" if not marks else ("amber" if len(marks) <= 2 else "red")
    codes = [m[0] for m in marks]
    if not marks:
        return _check("ingredients", color, ("Plain ingredients", "सादी सामग्री"),
                      [("Nothing a home kitchen would not have", "ऐसा कुछ नहीं जो घर की रसोई में न हो")], markers=codes)
    base = [m for m in marks if not m[0].startswith("additive:")]
    adds = [m for m in marks if m[0].startswith("additive:")]
    points = [(m[1][0].upper() + m[1][1:], m[2]) for m in base]
    if adds:
        n = len(adds)
        points.append((f"{n} kind{'s' if n > 1 else ''} of additive: {', '.join(m[1] for m in adds)}",
                       f"{n} तरह के एडिटिव: {', '.join(m[2] for m in adds)}"))
    head = ("Heavily processed", "बहुत ज़्यादा प्रोसेस्ड") if color == "red" else ("Somewhat processed", "कुछ हद तक प्रोसेस्ड")
    return _check("ingredients", color, head, points, markers=codes)


def _good(per100: dict, serving_g: float | None, is_liquid: bool, cat_text: str = "") -> dict:
    kind = "liquid" if is_liquid else "solid"
    protein, fibre = per100.get("protein_g"), per100.get("dietary_fibre_g")
    energy = per100.get("energy_kcal")
    if energy is not None and energy <= ENERGY_FREE_KCAL and not (protein or fibre):
        return _check("good", "grey", ("Nothing to look for", "यहाँ देखने को कुछ नहीं"),
                      [("It has no calories", "इसमें कैलोरी ही नहीं है")], protein_level=None, fibre_level=None)
    if protein is None and fibre is None:
        return _check("good", "grey", ("Not printed on the pack", "पैकेट पर नहीं लिखा"), [],
                      protein_level=None, fibre_level=None)
    p_pct100 = _pct(protein, FSSAI_RDA["protein_g"])

    def level(v, cut):
        return None if v is None else ("high" if v >= cut[1] else ("source" if v >= cut[0] else "low"))

    p_lvl, f_lvl = level(p_pct100, PROTEIN_PCT[kind]), level(fibre, FIBRE_G[kind])
    levels = {p_lvl, f_lvl}
    best = "high" if "high" in levels else ("source" if "source" in levels else "low")
    color = {"high": "green", "source": "amber", "low": "red"}[best]
    if color == "red" and re.search(COOKING_FAT, cat_text, flags=re.IGNORECASE):
        return _check("good", "grey", ("Not judged", "जाँच नहीं की गई"),
                      [("A cooking fat: nobody eats it for protein or fibre", "यह पकाने का तेल या घी है, इसे प्रोटीन या फ़ाइबर के लिए कोई नहीं खाता")],
                      protein_level=p_lvl, fibre_level=f_lvl)
    word = {"high": "high", "source": "some", "low": "very little"}
    word_hi = {"high": "भरपूर", "source": "कुछ", "low": "बहुत कम"}
    parts = [("protein", "प्रोटीन", p_lvl, protein, FSSAI_RDA["protein_g"]), ("fibre", "फ़ाइबर", f_lvl, fibre, FSSAI_RDA["dietary_fibre_g"])]
    parts = [p for p in parts if p[2] is not None]
    points: list[tuple[str, str]] = []
    for name, name_hi, lvl, v, day in parts:
        pct = _pct(per_serving(v, serving_g), day)
        tail = f", {pct:.0f}% of a day in one serve" if pct is not None and lvl != "low" else ""
        tail_hi = f", एक सर्व में दिन का {pct:.0f}%" if pct is not None and lvl != "low" else ""
        points.append((f"{name.capitalize()}: {word[lvl]}{tail}", f"{name_hi}: {word_hi[lvl]}{tail_hi}"))
    names = [p[0] for p in parts if p[2] == best]
    names_hi = [p[1] for p in parts if p[2] == best]
    start = {"high": "High in", "source": "Some", "low": "Very little"}[best]
    head = (f"{start} {_join(names, ' and ' if best != 'low' else ' or ')}", f"{_join(names_hi, ' और ')} {word_hi[best]}")
    return _check("good", color, head, points, protein_level=p_lvl, fibre_level=f_lvl)


# ---------------------------------------------------------------------------------------------
NAMES = {"sugar": ("Sugar", "चीनी"), "fat_salt": ("Fat and salt", "फ़ैट और नमक"),
         "ingredients": ("Ingredients", "सामग्री"), "good": ("Good stuff", "अच्छी चीज़ें")}
WORDS = {"green": ("Healthy", "सेहतमंद"), "amber": ("Okay, sometimes", "कभी-कभी ठीक है"),
         "red": ("Not healthy", "सेहतमंद नहीं"), "grey": ("Not enough info", "जानकारी कम है")}
ADVICE = {"green": ("Fine for every day.", "रोज़ खाने के लिए ठीक है।"),
          "amber": ("Okay now and then, one serve at a time. Not every day.", "कभी-कभी ठीक है, एक बार में एक सर्व। रोज़ नहीं।"),
          "red": ("Keep it for once in a while.", "इसे कभी-कभार के लिए रखिए।"),
          "grey": ("The pack prints too little to judge.", "पैकेट पर इतना कम लिखा है कि तय नहीं हो सकता।")}
LIMIT_NAMES = {"sugar": ("sugar", "चीनी"), "satfat": ("saturated fat", "सैचुरेटेड फ़ैट"), "sodium": ("salt", "नमक")}


def health_check(per100: dict, sugar: dict, serving_g: float | None, is_liquid: bool, ingredients: list[dict],
                 cat_text: str = "", n_sugar_names: int = 0) -> dict:
    """Four lights, the counting verdict, and how far one serve goes towards a day's limits."""
    ing_text = " ; ".join((i.get("name") or "") for i in ingredients)
    checks = [_sugar(per100, sugar, serving_g, is_liquid, ing_text, cat_text, n_sugar_names),
              _fat_salt(per100, serving_g, is_liquid, ing_text, cat_text), _ingredients(ingredients),
              _good(per100, serving_g, is_liquid, cat_text)]
    for c in checks:
        c["name"], c["name_hi"] = NAMES[c["key"]]
    seen = [c for c in checks if c["color"] != "grey"]
    reds = sum(c["color"] == "red" for c in seen)
    ambers = sum(c["color"] == "amber" for c in seen)
    # a verdict needs the nutrition table: at least one of the two "limit" checks, and two checks in all
    if len(seen) < 2 or all(c["color"] == "grey" for c in checks[:2]):
        color = "grey"
    elif reds >= 2:
        color = "red"
    elif reds == 1 or ambers >= 2:
        color = "amber"
    else:
        color = "green"

    pct = {"sugar": checks[0]["pct_day"], "satfat": checks[1]["satfat_pct_day"], "sodium": checks[1]["sodium_pct_day"]}
    known = {k: v for k, v in pct.items() if v is not None}
    en, hi = ADVICE[color]
    if known:
        k = max(known, key=known.get)
        top = known[k]
        name, name_hi = LIMIT_NAMES[k]
        if top >= 100:
            en = f"One serve is already more than a full day's {name}. " + en
            hi = f"एक सर्व में ही पूरे दिन से ज़्यादा {name_hi} है। " + hi
        elif top >= 100 / 6:
            n = math.ceil(100 / top)
            en = f"{n} serves = a full day's {name}. " + en
            hi = f"{n} सर्व = पूरे दिन का {name_hi}। " + hi
        elif top >= 5:
            en = f"One serve is {top:.0f}% of a day's {name}. " + en
            hi = f"एक सर्व = दिन के {name_hi} का {top:.0f}%। " + hi
    return {"checks": checks, "color": color, "word": WORDS[color][0], "word_hi": WORDS[color][1],
            "reds": reds, "ambers": ambers, "pct_day_per_serve": pct, "how_much": en, "how_much_hi": hi}
