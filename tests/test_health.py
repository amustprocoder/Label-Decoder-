"""
Health-check tests: four lights and the counting verdict. Synthetic labels again, so each test pins one rule.
Run: pytest -q
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import ui  # noqa: E402
from src.rules import health  # noqa: E402
from src.rules.decoder import decode_label, split_ingredients  # noqa: E402


def check(label):
    h = decode_label(label)["health"]
    return h, {c["key"]: c["color"] for c in h["checks"]}


OATS = {"product_name": "Rolled Oats", "category": "oats", "serving_size_g": 40,
        "per_100": {"energy_kcal": 380, "protein_g": 12, "total_sugars_g": 1, "dietary_fibre_g": 10,
                    "saturated_fat_g": 1.4, "trans_fat_g": 0, "sodium_mg": 5},
        "ingredients_text": "Rolled oats (100%)", "front_of_pack_claims": []}
BISCUIT = {"product_name": "Cream Biscuit", "category": "biscuit", "serving_size_g": 30,
           "per_100": {"energy_kcal": 480, "protein_g": 5, "total_sugars_g": 36, "dietary_fibre_g": 1,
                       "saturated_fat_g": 11, "trans_fat_g": 0.1, "sodium_mg": 250},
           "ingredients_text": "Refined wheat flour (Maida), Sugar, Palm oil, Invert syrup, Emulsifier (INS 322), "
                               "Artificial flavouring substances (Vanilla), Colour (INS 150d)",
           "front_of_pack_claims": []}


# ---------------------------------------------------------------- the verdict only counts the lights
def test_plain_oats_are_healthy():
    h, c = check(OATS)
    assert c == {"sugar": "green", "fat_salt": "green", "ingredients": "green", "good": "green"}
    assert (h["color"], h["word"]) == ("green", "Healthy")


def test_cream_biscuit_is_not_healthy():
    h, c = check(BISCUIT)
    assert c["sugar"] == "red" and c["fat_salt"] == "red" and c["ingredients"] == "red"
    assert h["color"] == "red" and h["reds"] >= 2


def test_one_red_is_okay_sometimes():
    # plain salted nuts: high saturated fat is the only red
    nuts = {"product_name": "Roasted Cashews", "category": "nuts", "serving_size_g": 30,
            "per_100": {"energy_kcal": 590, "protein_g": 19, "total_sugars_g": 5, "dietary_fibre_g": 3.5,
                        "saturated_fat_g": 8.5, "sodium_mg": 10},
            "ingredients_text": "Cashew nuts", "front_of_pack_claims": []}
    h, c = check(nuts)
    assert c["fat_salt"] == "red" and list(c.values()).count("red") == 1
    assert h["word"] == "Okay, sometimes"


def test_two_yellows_are_okay_sometimes():
    bread = {"product_name": "White Bread", "category": "bread", "serving_size_g": 50,
             "per_100": {"energy_kcal": 250, "protein_g": 8, "total_sugars_g": 4, "dietary_fibre_g": 2,
                         "saturated_fat_g": 0.5, "sodium_mg": 400},
             "ingredients_text": "Refined wheat flour (Maida), Water, Yeast, Salt", "front_of_pack_claims": []}
    h, c = check(bread)
    assert "red" not in c.values() and list(c.values()).count("amber") >= 2
    assert h["word"] == "Okay, sometimes"


def test_too_little_printed_gives_no_verdict():
    h, c = check({"product_name": "Mystery Snack", "per_100": {}, "ingredients_text": "", "front_of_pack_claims": []})
    assert set(c.values()) == {"grey"} and h["word"] == "Not enough info"
    assert ui.verdict({"health": h, "flags": []}, {})[1] == "Not enough info"


# ---------------------------------------------------------------- sugar
def test_one_serve_can_turn_sugar_red_on_its_own():
    # 9 g per 100 ml is yellow on the per-100 scale; a 300 ml bottle is 27 g, more than a day's 25 g
    drink = {"product_name": "Mango Drink", "category": "juice drink", "is_liquid": True, "serving_size_g": 300,
             "per_100": {"energy_kcal": 40, "total_sugars_g": 9, "protein_g": 0}, "ingredients_text": "Water, Mango pulp, Sugar",
             "front_of_pack_claims": []}
    h, c = check(drink)
    assert c["sugar"] == "red" and h["pct_day_per_serve"]["sugar"] > 100
    assert "more than a full day's sugar" in h["how_much"]


def test_milk_sugar_is_not_counted_as_free_sugar():
    milk = {"product_name": "Toned Milk", "category": "milk", "is_liquid": True, "serving_size_g": 200,
            "per_100": {"energy_kcal": 58, "protein_g": 3.1, "total_sugars_g": 4.8, "saturated_fat_g": 1.9, "sodium_mg": 40},
            "ingredients_text": "Toned milk", "front_of_pack_claims": []}
    _, c = check(milk)
    assert c["sugar"] == "green"


def test_sugar_under_two_names_is_never_green():
    snack = {"product_name": "Masala Snack", "category": "namkeen", "serving_size_g": 30,
             "per_100": {"total_sugars_g": 4, "saturated_fat_g": 1, "sodium_mg": 50, "protein_g": 12},
             "ingredients_text": "Gram flour, Rice bran oil, Sugar, Dextrose, Spices", "front_of_pack_claims": []}
    _, c = check(snack)
    assert c["sugar"] == "amber"


# ---------------------------------------------------------------- fat and salt
def test_trans_fat_above_the_free_limit_is_red_but_milk_fat_is_exempt():
    fried = {"product_name": "Fried Snack", "category": "namkeen", "per_100": {"saturated_fat_g": 1, "trans_fat_g": 0.5, "sodium_mg": 50},
             "ingredients_text": "Gram flour, Vegetable oil", "front_of_pack_claims": []}
    doi = {"product_name": "Mishti Doi", "category": "yogurt", "per_100": {"saturated_fat_g": 1, "trans_fat_g": 0.25, "sodium_mg": 50},
           "ingredients_text": "Milk, Sugar", "front_of_pack_claims": []}
    assert check(fried)[1]["fat_salt"] == "red"
    assert check(doi)[1]["fat_salt"] == "green"


def test_salty_serve_is_red_even_when_per_100_is_only_yellow():
    # 400 mg sodium per 100 g is 1 g salt (yellow); a 150 g ready meal is 630 mg, over 30% of a day
    meal = {"product_name": "Ready Meal", "category": "ready meal", "serving_size_g": 150,
            "per_100": {"saturated_fat_g": 1, "sodium_mg": 420, "protein_g": 6, "total_sugars_g": 1},
            "ingredients_text": "Rice, Chickpeas, Onion, Salt", "front_of_pack_claims": []}
    h, c = check(meal)
    assert c["fat_salt"] == "red" and h["pct_day_per_serve"]["sodium"] >= 30


# ---------------------------------------------------------------- ingredients
def test_ingredient_markers():
    marks = {m[0] for m in health.ingredient_markers(split_ingredients(BISCUIT["ingredients_text"]))}
    assert {"refined_flour_first", "palm_oil", "industrial:invert syrup", "additive:emulsifier",
            "additive:added flavour", "additive:colour"} <= marks
    # palm oil hidden inside "edible vegetable oil (palmolein)" still counts; preservatives do not
    chips = split_ingredients("Potato, Edible vegetable oil (Palmolein), Salt, Preservative (INS 211), Antioxidant (INS 319)")
    assert [m[0] for m in health.ingredient_markers(chips)] == ["palm_oil"]


def test_one_or_two_markers_are_yellow_three_are_red():
    def colour(text):
        return check({"product_name": "X", "per_100": {"total_sugars_g": 1}, "ingredients_text": text,
                      "front_of_pack_claims": []})[1]["ingredients"]
    assert colour("Whole wheat flour, Water, Salt") == "green"
    assert colour("Whole wheat flour, Water, Salt, Emulsifier (INS 471)") == "amber"
    assert colour("Maida, Palm oil, Salt, Flavour enhancer (INS 627)") == "red"


# ---------------------------------------------------------------- good stuff
def test_good_stuff_uses_the_fssai_source_and_high_levels():
    def colour(protein, fibre):
        return check({"product_name": "X", "per_100": {"energy_kcal": 300, "protein_g": protein, "dietary_fibre_g": fibre,
                                                       "total_sugars_g": 1}, "front_of_pack_claims": []})[1]["good"]
    assert colour(11, 1) == "green"       # 20% of the 54 g RDA is 10.8 g
    assert colour(6, 1) == "amber"        # 10% is 5.4 g
    assert colour(2, 6.5) == "green"      # high in fibre from 6 g
    assert colour(2, 1) == "red"


def test_water_and_cooking_oil_are_not_marked_down_for_protein():
    water = {"product_name": "Drinking Water", "category": "water", "is_liquid": True,
             "per_100": {"energy_kcal": 0, "protein_g": 0, "total_sugars_g": 0, "saturated_fat_g": 0, "sodium_mg": 1},
             "ingredients_text": "Treated water, Minerals", "front_of_pack_claims": []}
    oil = {"product_name": "Mustard Oil", "category": "oil", "is_liquid": True,
           "per_100": {"energy_kcal": 900, "protein_g": 0, "total_sugars_g": 0, "saturated_fat_g": 12, "sodium_mg": 0},
           "ingredients_text": "Mustard oil", "front_of_pack_claims": []}
    hw, cw = check(water)
    assert cw["good"] == "grey" and hw["word"] == "Healthy"
    assert check(oil)[1]["good"] == "grey"


# ---------------------------------------------------------------- consistency
def test_cut_offs_match_the_traffic_light_card():
    for k in ("sugar", "satfat", "salt"):
        assert health.FSA_FOOD[k] == ui.FSA_FOOD[k] and health.FSA_DRINK[k] == ui.FSA_DRINK[k]


def test_same_label_same_health_verdict():
    assert decode_label(BISCUIT)["health"] == decode_label(BISCUIT)["health"]
