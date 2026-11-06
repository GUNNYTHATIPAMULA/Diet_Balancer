export const MEAL_TYPES = [
  { value: "breakfast", label: "Breakfast" },
  { value: "lunch", label: "Lunch" },
  { value: "dinner", label: "Dinner" },
  { value: "snacks", label: "Snacks" },
];
export const mealLabel = (v) => MEAL_TYPES.find((m) => m.value === v)?.label ?? v;

export const ACTIVITY_LEVELS = [
  { value: "sedentary", label: "Sedentary", hint: "Desk job, little exercise", factor: 1.2 },
  { value: "lightly_active", label: "Lightly active", hint: "Light exercise 1–3 days a week", factor: 1.375 },
  { value: "moderately_active", label: "Moderately active", hint: "Moderate exercise 3–5 days a week", factor: 1.55 },
  { value: "very_active", label: "Very active", hint: "Hard exercise 6–7 days a week", factor: 1.725 },
  { value: "extra_active", label: "Extra active", hint: "Physical job plus daily training", factor: 1.9 },
];

export const GOALS = [
  { value: "maintain", label: "Maintain weight", hint: "Eat at your estimated maintenance level" },
  { value: "lose", label: "Lose weight", hint: "A modest, sustainable deficit" },
  { value: "gain", label: "Gain weight", hint: "A small surplus for steady gain" },
];

export const PACES = [
  { value: "gentle", label: "Gentle", hint: "Smaller change, easier to sustain" },
  { value: "moderate", label: "Moderate", hint: "Capped at 500 kcal less or 350 kcal more" },
];

export const DIET_PREFERENCES = [
  { value: "none", label: "No preference" },
  { value: "vegetarian", label: "Vegetarian" },
  { value: "eggetarian", label: "Eggetarian" },
  { value: "vegan", label: "Vegan" },
  { value: "non_vegetarian", label: "Non-vegetarian" },
];

export const ALLERGENS = [
  { value: "dairy", label: "Dairy" },
  { value: "egg", label: "Egg" },
  { value: "gluten", label: "Gluten" },
  { value: "peanut", label: "Peanut" },
  { value: "tree_nut", label: "Tree nuts" },
  { value: "soy", label: "Soy" },
  { value: "sesame", label: "Sesame" },
  { value: "fish", label: "Fish" },
  { value: "shellfish", label: "Shellfish" },
];

export const DIET_TYPE_LABELS = {
  vegan: "Vegan",
  vegetarian: "Vegetarian",
  eggetarian: "Contains egg",
  non_vegetarian: "Non-veg",
};

export const MACRO_COLORS = { protein: "#2F6E8F", carbs: "#C9962B", fat: "#9A5B8C", calories: "#3E8E5E" };

export const DISCLAIMER =
  "Calorie and macro targets are estimates, not medical advice. Talk to a doctor or registered dietitian before making significant changes.";
