"""
Rules-layer tests. Each case is a label pattern seen on Indian shelves, written as a synthetic
label so the test pins the rule, not a brand. Run: pytest -q
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.rules.decoder import decode_label, split_ingredients  # noqa: E402
from src.rules.fssai_claims import detect_claims  # noqa: E402
from src.rules.sugar_aliases import classify_ingredient, consolidated_rank, find_sugars  # noqa: E402


def codes(result):
    return {f["code"] for f in result["flags"]}


# ---------------------------------------------------------------- ingredient parsing
def test_split_handles_nested_brackets_and_percent():
    items = split_ingredients("Refined wheat flour (Maida), Sugar, Choco chips 8% (Sugar, Cocoa solids, "
                              "Emulsifier (INS 322)), Invert syrup, Salt")
    names = [i["name"] for i in items]
    assert names[0] == "Refined wheat flour"
    assert {"name": "Maida", "percent": None, "nested": True, "parent": "Refined wheat flour"} in items
    choco = next(i for i in items if i["name"].startswith("Choco"))
    assert choco["percent"] == 8.0
    assert any(i["name"] == "Sugar" and i.get("nested") for i in items)      # the sugar inside choco chips
    assert "Emulsifier" in names and "INS 322" not in names


def test_nested_items_inherit_parent_rank():
    items = split_ingredients("Oats, Choco chips (Sugar, Cocoa), Honey")
    hits = find_sugars(items)
    by = {h.canonical: h.position for h in hits}
    assert by["sugar (sucrose)"] == 2 and by["honey"] == 3


# ---------------------------------------------------------------- sugar aliases
def test_aliases_hit_hindi_and_industrial_names():
    for line, tier in [("Gur", "added"), ("Liquid glucose", "added"), ("Invert syrup", "added"),
                       ("Dextrose monohydrate", "added"), ("Apple juice concentrate", "added"),
                       ("Maltodextrin", "sugar_like"), ("Sucralose (INS 955)", "sweetener"),
                       ("Maltitol", "sweetener"), ("Sweetener (960)", "sweetener")]:
        res = classify_ingredient(line)
        assert res and res[1] == tier, line


def test_whole_foods_are_not_added_sugar():
    assert classify_ingredient("Milk solids") is None
    assert classify_ingredient("Banana") is None
    assert classify_ingredient("Fruit pulp") is None
    assert classify_ingredient("Sugar free") is None


def test_split_sugar_consolidates_to_top():
    items = split_ingredients("Wheat flour, Sugar, Vegetable oil, Liquid glucose, Invert syrup, Dextrose, Salt")
    hits = find_sugars(items)
    r = consolidated_rank(items, hits)
    assert r["n_added_sugar_lines"] == 4 and r["combined_rank_estimate"] <= 2


def test_consolidation_uses_declared_percentages():
    items = [{"name": "Oats", "percent": 45}, {"name": "Sugar", "percent": 15}, {"name": "Honey", "percent": 12},
             {"name": "Nuts", "percent": 20}]
    r = consolidated_rank(items, find_sugars(items))
    assert r["combined_percent"] == 27 and r["combined_rank_estimate"] == 2   # oats 45% stays #1, sugar 27% beats nuts 20%


# ---------------------------------------------------------------- claim detection
def test_claim_detection_maps_wording():
    det = {c for _, c, k in detect_claims(["No Added Sugar", "High in Protein", "Zero Trans Fat", "100% Natural",
                                           "Made with real fruit", "Immunity booster"])}
    assert {"no added sugar", "high protein", "trans fat free", "natural", "real fruit", "immunity"} <= det


# ---------------------------------------------------------------- decoder verdicts
BASE = {"product_name": "Test", "category": "biscuit", "is_liquid": False, "serving_size_g": 25}


def test_high_protein_per_100_but_not_per_serve():
    label = dict(BASE, per_100={"energy_kcal": 450, "protein_g": 12, "total_sugars_g": 20},
                 ingredients_text="Wheat flour, Sugar, Oil, Whey protein", front_of_pack_claims=["High Protein"])
    r = decode_label(label)
    c = r["claims"][0]
    assert c["claim_type"] == "high protein" and c["verdict"] == "legal but misleading"
    assert "PER100_VS_SERVE" in codes(r)


def test_high_protein_fails_outright():
    label = dict(BASE, per_100={"protein_g": 6, "total_sugars_g": 20}, ingredients_text="Wheat flour, Sugar",
                 front_of_pack_claims=["Protein rich"])
    assert decode_label(label)["claims"][0]["verdict"] == "fails"


def test_no_added_sugar_with_fruit_concentrate_is_flagged():
    label = dict(BASE, category="juice", is_liquid=True, serving_size_g=200,
                 per_100={"total_sugars_g": 11}, ingredients_text="Water, Apple juice concentrate, Mango pulp",
                 front_of_pack_claims=["No added sugar"])
    r = decode_label(label)
    assert "NAS_SUBSTITUTE" in codes(r)


def test_no_added_sugar_juice_still_high_sugar_per_serve():
    label = dict(BASE, category="juice", is_liquid=True, serving_size_g=200,
                 per_100={"total_sugars_g": 11}, ingredients_text="Mango pulp (25%), Water",
                 front_of_pack_claims=["No added sugar"])
    r = decode_label(label)
    assert "NAS_HIGH_INTRINSIC" in codes(r) and "NAS_SUBSTITUTE" not in codes(r)
    assert abs(r["sugar"]["teaspoons_total_per_serve"] - 5.5) < 0.01


def test_sugar_free_polyol_gets_laxative_note():
    label = dict(BASE, per_100={"total_sugars_g": 0.3}, ingredients_text="Wheat flour, Maltitol, Oil, Sucralose (955)",
                 front_of_pack_claims=["Sugar Free"])
    r = decode_label(label)
    assert r["claims"][0]["verdict"] == "holds" and "SUGAR_FREE_POLYOL" in codes(r)


def test_healthy_halo_over_sugar_top_ingredient():
    label = dict(BASE, category="health drink", serving_size_g=20,
                 per_100={"total_sugars_g": 36, "protein_g": 7, "energy_kcal": 380},
                 ingredients_text="Malt extract, Sugar, Milk solids (9%), Cocoa, Liquid glucose",
                 front_of_pack_claims=["Healthy growth", "Immunity"])
    r = decode_label(label)
    assert {"SUGAR_SPLIT", "HALO_OVER_SUGAR", "IMMUNITY_CLAIM"} <= codes(r)
    assert r["sugar"]["added_sugars_per_100"] is not None and r["sugar"]["added_sugars_per_100"] < 36


def test_multigrain_with_maida_first():
    label = dict(BASE, per_100={"total_sugars_g": 15}, ingredients_text="Refined wheat flour (maida), Sugar, Oats (4%), Ragi (2%)",
                 front_of_pack_claims=["Multigrain"])
    assert "MULTIGRAIN_MAIDA" in codes(decode_label(label))


def test_natural_with_additives():
    label = dict(BASE, per_100={"total_sugars_g": 15}, ingredients_text="Fruit pulp, Sugar, Acidity regulator (INS 330), Flavour",
                 front_of_pack_claims=["100% Natural"])
    assert "NATURAL_WITH_ADDITIVES" in codes(decode_label(label))


def test_cholesterol_free_on_plant_food():
    label = dict(BASE, category="chips", per_100={"total_sugars_g": 1, "cholesterol_mg": 0, "total_fat_g": 33},
                 ingredients_text="Potato, Edible vegetable oil, Salt", front_of_pack_claims=["0 Cholesterol"])
    r = decode_label(label)
    assert r["claims"][0]["verdict"] == "holds" and "CHOLESTEROL_FREE_PLANT" in codes(r)


def test_who_limit_and_teaspoon_maths():
    label = dict(BASE, category="soft drink", is_liquid=True, serving_size_g=300,
                 per_100={"total_sugars_g": 10.6}, ingredients_text="Carbonated water, Sugar, Acidity regulator (338)",
                 front_of_pack_claims=[])
    r = decode_label(label)
    assert abs(r["sugar"]["total_sugars_per_serve"] - 31.8) < 0.01
    assert "WHO_LIMIT_BLOWN" in codes(r)


def test_salt_converts_to_sodium():
    label = dict(BASE, per_100={"salt_g": 2.5, "total_sugars_g": 1}, ingredients_text="Potato, Oil, Salt",
                 front_of_pack_claims=["Low sodium"])
    r = decode_label(label)
    assert r["claims"][0]["actual_per_100"] == 1000 and r["claims"][0]["verdict"] == "fails"


def test_tiny_serving_flag():
    label = dict(BASE, category="chips", serving_size_g=10, per_100={"total_sugars_g": 1, "total_fat_g": 30},
                 ingredients_text="Potato, Oil, Salt", front_of_pack_claims=[])
    assert "SERVING_TINY" in codes(decode_label(label))


def test_assumed_serving_when_pack_declares_none():
    label = {"product_name": "X", "category": "biscuit", "per_100": {"total_sugars_g": 24},
             "ingredients_text": "Wheat flour, Sugar", "front_of_pack_claims": []}
    r = decode_label(label)
    assert r["serving"]["g"] == 30 and "assumed" in r["serving"]["source"]
    assert abs(r["sugar"]["teaspoons_total_per_serve"] - 1.8) < 0.01


def test_same_input_same_output():
    label = dict(BASE, per_100={"total_sugars_g": 24, "protein_g": 8}, ingredients_text="Wheat flour, Sugar, Honey",
                 front_of_pack_claims=["Protein", "Healthy"])
    assert decode_label(label) == decode_label(label)


def test_crowd_liquid_tag_ignored_for_solid_foods():
    noodles = {"product_name": "2 - Minute Noodles", "category": "pot noodles", "is_liquid": True,
               "per_100": {"total_sugars_g": 1.8}, "ingredients_text": "Maida, Palm oil", "front_of_pack_claims": []}
    lassi = {"product_name": "Amul Lassi", "category": "yogurt drinks", "is_liquid": True,
             "per_100": {"total_sugars_g": 22.5}, "ingredients_text": "Milk solids, water, sugar", "front_of_pack_claims": []}
    assert decode_label(noodles)["product"]["is_liquid"] is False
    assert decode_label(lassi)["product"]["is_liquid"] is True


def test_flavour_and_colour_are_not_sugar():
    hits = find_sugars(split_ingredients("Sugar, Cocoa solids, Caramel colour (150d), Flavours (Caramel and Vanilla)"))
    assert [h.canonical for h in hits] == ["sugar (sucrose)"]
