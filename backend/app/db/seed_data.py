"""Starter food catalogue.

IMPORTANT: every value below is an APPROXIMATE reference value per 100 g, rounded,
compiled from USDA FoodData Central (SR Legacy / Foundation) and the Indian Food
Composition Tables (IFCT 2017, National Institute of Nutrition, ICMR). Home-cooked
Indian dishes vary a lot with recipe, oil and water content, so every item is
stored with is_approximate=True and its source. Verify against a lab-tested or
package-label value before relying on any number for clinical purposes.

Columns: name, category, kcal, protein, carbs, fat, fiber, serving_unit,
serving_size_g, diet_type, allergens, source_key
"""

SOURCES = {
    "usda": "Approximate; USDA FoodData Central (SR Legacy/Foundation), rounded",
    "ifct": "Approximate; Indian Food Composition Tables 2017 (NIN-ICMR), rounded",
    "recipe": "Approximate; typical home recipe estimate cross-checked with IFCT 2017 and USDA; varies by recipe",
    "label": "Approximate; typical Indian retail package label values; check your brand",
}

FOODS = [
    # Grains & cereals ---------------------------------------------------------
    ("White rice, cooked", "Grains", 130, 2.7, 28.2, 0.3, 0.4, "1 cup", 160, "vegan", [], "usda"),
    ("White rice, raw (dry)", "Grains", 365, 7.1, 80.0, 0.7, 1.3, "1/4 cup dry", 45, "vegan", [], "usda"),
    ("Brown rice, raw (dry)", "Grains", 370, 7.9, 77.2, 2.9, 3.5, "1/4 cup dry", 45, "vegan", [], "usda"),
    ("Brown rice, cooked", "Grains", 112, 2.3, 23.5, 0.8, 1.8, "1 cup", 160, "vegan", [], "usda"),
    ("Roti / chapati (whole wheat, no ghee)", "Grains", 264, 9.0, 52.0, 2.3, 4.9, "1 medium roti", 40, "vegan",
     ["gluten"], "recipe"),
    ("Rolled oats (dry)", "Grains", 379, 13.2, 67.7, 6.5, 10.1, "1/2 cup dry", 40, "vegan", ["gluten"], "usda"),
    ("Oats porridge, cooked in water", "Grains", 71, 2.5, 12.0, 1.5, 1.7, "1 bowl", 240, "vegan", ["gluten"], "usda"),
    ("Poha (flattened rice, dry)", "Grains", 350, 6.6, 77.0, 1.2, 1.0, "1/2 cup dry", 40, "vegan", [], "ifct"),
    ("Semolina / rava (dry)", "Grains", 360, 12.7, 72.8, 1.1, 3.9, "1/4 cup dry", 40, "vegan", ["gluten"], "usda"),
    ("Whole wheat bread", "Grains", 252, 12.5, 42.7, 3.5, 6.0, "1 slice", 30, "vegan", ["gluten"], "usda"),
    # South Indian -------------------------------------------------------------
    ("Idli", "South Indian", 130, 4.0, 27.0, 0.5, 1.0, "1 idli", 40, "vegan", [], "recipe"),
    ("Plain dosa", "South Indian", 168, 3.9, 29.0, 3.9, 1.0, "1 dosa", 80, "vegan", [], "recipe"),
    # Pulses & legumes ---------------------------------------------------------
    ("Dal (toor/arhar), cooked plain", "Pulses", 116, 9.0, 20.1, 0.4, 7.9, "1 katori", 150, "vegan", [], "usda"),
    ("Moong dal, cooked", "Pulses", 105, 7.0, 19.2, 0.4, 7.6, "1 katori", 150, "vegan", [], "usda"),
    ("Rajma (kidney beans), cooked", "Pulses", 127, 8.7, 22.8, 0.5, 6.4, "1 katori", 150, "vegan", [], "usda"),
    ("Chana (chickpeas), cooked", "Pulses", 164, 8.9, 27.4, 2.6, 7.6, "1 katori", 150, "vegan", [], "usda"),
    ("Moong sprouts, raw", "Pulses", 30, 3.0, 5.9, 0.2, 1.8, "1 cup", 100, "vegan", [], "usda"),
    ("Roasted chana (Bengal gram)", "Pulses", 369, 22.5, 58.0, 5.2, 16.8, "1 handful", 30, "vegan", [], "ifct"),
    ("Soya chunks (dry)", "Pulses", 345, 52.0, 33.0, 0.5, 13.0, "1/2 cup dry", 25, "vegan", ["soy"], "label"),
    ("Tofu, firm", "Pulses", 144, 17.3, 2.8, 8.7, 2.3, "100 g", 100, "vegan", ["soy"], "usda"),
    # Dairy ----------------------------------------------------------------------
    ("Paneer", "Dairy", 265, 18.3, 1.2, 20.8, 0.0, "50 g piece", 50, "vegetarian", ["dairy"], "ifct"),
    ("Milk, toned (about 3% fat)", "Dairy", 58, 3.1, 4.7, 3.0, 0.0, "1 glass", 200, "vegetarian", ["dairy"],
     "label"),
    ("Milk, whole (cow)", "Dairy", 61, 3.2, 4.8, 3.3, 0.0, "1 glass", 200, "vegetarian", ["dairy"], "usda"),
    ("Curd / dahi (whole milk)", "Dairy", 61, 3.5, 4.7, 3.3, 0.0, "1 katori", 150, "vegetarian", ["dairy"], "usda"),
    ("Ghee", "Fats & oils", 876, 0.3, 0.0, 99.5, 0.0, "1 tsp", 5, "vegetarian", ["dairy"], "usda"),
    # Eggs & meat --------------------------------------------------------------
    ("Egg, whole, boiled", "Eggs", 155, 12.6, 1.1, 10.6, 0.0, "1 large egg", 50, "eggetarian", ["egg"], "usda"),
    ("Egg white, boiled", "Eggs", 52, 10.9, 0.7, 0.2, 0.0, "2 whites", 66, "eggetarian", ["egg"], "usda"),
    ("Chicken breast, cooked (skinless)", "Meat & fish", 165, 31.0, 0.0, 3.6, 0.0, "1 piece", 100,
     "non_vegetarian", [], "usda"),
    # Fruit ----------------------------------------------------------------------
    ("Banana", "Fruit", 89, 1.1, 22.8, 0.3, 2.6, "1 medium", 118, "vegan", [], "usda"),
    ("Apple (with skin)", "Fruit", 52, 0.3, 13.8, 0.2, 2.4, "1 medium", 180, "vegan", [], "usda"),
    ("Orange", "Fruit", 47, 0.9, 11.8, 0.1, 2.4, "1 medium", 130, "vegan", [], "usda"),
    ("Papaya", "Fruit", 43, 0.5, 10.8, 0.3, 1.7, "1 cup", 145, "vegan", [], "usda"),
    ("Guava", "Fruit", 68, 2.6, 14.3, 1.0, 5.4, "1 medium", 100, "vegan", [], "usda"),
    ("Mango", "Fruit", 60, 0.8, 15.0, 0.4, 1.6, "1 cup", 165, "vegan", [], "usda"),
    ("Dates", "Fruit", 282, 2.5, 75.0, 0.4, 8.0, "3 dates", 24, "vegan", [], "usda"),
    # Vegetables -----------------------------------------------------------------
    ("Spinach (palak), raw", "Vegetables", 23, 2.9, 3.6, 0.4, 2.2, "1 cup", 30, "vegan", [], "usda"),
    ("Mixed vegetables, boiled", "Vegetables", 65, 2.9, 13.1, 0.2, 4.4, "1 cup", 180, "vegan", [], "usda"),
    ("Cauliflower, raw", "Vegetables", 25, 1.9, 5.0, 0.3, 2.0, "1 cup", 100, "vegan", [], "usda"),
    ("Carrot, raw", "Vegetables", 41, 0.9, 9.6, 0.2, 2.8, "1 medium", 60, "vegan", [], "usda"),
    ("Cucumber", "Vegetables", 15, 0.7, 3.6, 0.1, 0.5, "1/2 cucumber", 150, "vegan", [], "usda"),
    ("Tomato", "Vegetables", 18, 0.9, 3.9, 0.2, 1.2, "1 medium", 120, "vegan", [], "usda"),
    ("Potato, boiled", "Vegetables", 87, 1.9, 20.1, 0.1, 1.8, "1 medium", 150, "vegan", [], "usda"),
    ("Sweet potato, boiled", "Vegetables", 76, 1.4, 17.7, 0.1, 2.5, "1 medium", 150, "vegan", [], "usda"),
    # Nuts & seeds -------------------------------------------------------------
    ("Almonds", "Nuts & seeds", 579, 21.2, 21.6, 49.9, 12.5, "10 almonds", 12, "vegan", ["tree_nut"], "usda"),
    ("Peanuts, raw", "Nuts & seeds", 567, 25.8, 16.1, 49.2, 8.5, "1 handful", 30, "vegan", ["peanut"], "usda"),
    ("Cashews", "Nuts & seeds", 553, 18.2, 30.2, 43.9, 3.3, "10 cashews", 15, "vegan", ["tree_nut"], "usda"),
    ("Walnuts", "Nuts & seeds", 654, 15.2, 13.7, 65.2, 6.7, "5 halves", 10, "vegan", ["tree_nut"], "usda"),
    ("Makhana (fox nuts), dry", "Nuts & seeds", 347, 9.7, 76.9, 0.1, 14.5, "1 cup", 15, "vegan", [], "ifct"),
]

# Other names people type (Hindi / Telugu / common English). Matching is case-insensitive.
ALIASES = {
    "White rice, raw (dry)": ["rice", "raw rice", "chawal", "biyyam", "uncooked rice"],
    "White rice, cooked": ["rice", "cooked rice", "chawal", "annam", "bhaat"],
    "Brown rice, raw (dry)": ["brown rice"],
    "Brown rice, cooked": ["brown rice"],
    "Roti / chapati (whole wheat, no ghee)": ["roti", "chapati", "phulka"],
    "Rolled oats (dry)": ["oats", "oatmeal", "raw oats"],
    "Oats porridge, cooked in water": ["oats", "porridge"],
    "Poha (flattened rice, dry)": ["poha", "flattened rice", "atukulu", "aval"],
    "Semolina / rava (dry)": ["rava", "sooji", "suji", "semolina"],
    "Dal (toor/arhar), cooked plain": ["dal", "toor dal", "arhar", "pappu"],
    "Moong dal, cooked": ["moong", "moong dal", "pesarapappu"],
    "Rajma (kidney beans), cooked": ["rajma", "kidney beans"],
    "Chana (chickpeas), cooked": ["chana", "chole", "chickpeas"],
    "Roasted chana (Bengal gram)": ["roasted chana", "bengal gram", "chana"],
    "Soya chunks (dry)": ["soya", "soya chunks", "meal maker"],
    "Paneer": ["cottage cheese"],
    "Milk, toned (about 3% fat)": ["milk", "doodh", "paalu"],
    "Milk, whole (cow)": ["milk", "doodh", "full cream milk"],
    "Curd / dahi (whole milk)": ["curd", "dahi", "yogurt", "perugu"],
    "Egg, whole, boiled": ["egg", "eggs", "anda", "guddu", "boiled egg"],
    "Egg white, boiled": ["egg white"],
    "Chicken breast, cooked (skinless)": ["chicken", "chicken breast"],
    "Banana": ["kela", "arati pandu"],
    "Almonds": ["badam", "almond"],
    "Peanuts, raw": ["peanut", "peanuts", "groundnut", "moongphali", "palli"],
    "Cashews": ["kaju", "cashew"],
    "Walnuts": ["akhrot", "walnut"],
    "Makhana (fox nuts), dry": ["makhana", "fox nuts", "lotus seeds"],
    "Dates": ["khajur", "kharjura"],
    "Spinach (palak), raw": ["palak", "spinach"],
}
