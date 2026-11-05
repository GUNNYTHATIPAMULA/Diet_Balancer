import { render } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { ToastProvider } from "../context/ToastContext";
import { AuthProvider } from "../context/AuthContext";

export function renderWithProviders(ui, { route = "/", path = "/", extraRoutes = null } = {}) {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <ToastProvider>
        <AuthProvider>
          <Routes>
            <Route path={path} element={ui} />
            {extraRoutes}
          </Routes>
        </AuthProvider>
      </ToastProvider>
    </MemoryRouter>,
  );
}

export const apiError = (status, message, code = "error", details = null) =>
  Object.assign(new Error(message), { response: { status, data: { error: { code, message, details } } } });

export const TARGETS = {
  formula: "Mifflin-St Jeor", bmr: 1400, activity_factor: 1.375, tdee: 1925, goal_type: "lose", goal_pace: "gentle",
  goal_adjustment: -193, calorie_floor: 1400, floor_applied: false, calorie_target: 1730, protein_g: 102, carbs_g: 205, fat_g: 52,
  fiber_g: 24, explanation: ["BMR = ..."], disclaimer: "Not medical advice.",
};

const totals = (c = 0) => ({ calories: c, protein_g: 0, carbs_g: 0, fat_g: 0, fiber_g: 0 });
export const SUMMARY = {
  date: "2026-11-04", has_profile: true, targets: TARGETS,
  consumed: { calories: 530, protein_g: 20, carbs_g: 80, fat_g: 12, fiber_g: 5 },
  remaining: { calories: 1200, protein_g: 82, carbs_g: 125, fat_g: 40, fiber_g: 19 },
  macro_split_percent: { protein: 16, carbs: 62, fat: 22 },
  meals: [
    { meal_type: "breakfast", totals: { calories: 530, protein_g: 20, carbs_g: 80, fat_g: 12, fiber_g: 5 }, entries: [
      { id: "e1", food_item_id: "f1", food_name: "Idli", food_category: "South Indian", meal_type: "breakfast", consumed_on: "2026-11-04",
        quantity_g: 160, calories: 208, protein_g: 6.4, carbs_g: 43.2, fat_g: 0.8, fiber_g: 1.6, source: "manual", dispensing_command_id: null, created_at: "2026-11-04T08:00:00Z" },
      { id: "e2", food_item_id: "f2", food_name: "Rolled oats (dry)", food_category: "Grains", meal_type: "breakfast", consumed_on: "2026-11-04",
        quantity_g: 85, calories: 322, protein_g: 11.2, carbs_g: 57.5, fat_g: 5.5, fiber_g: 8.6, source: "dispenser", dispensing_command_id: "c1", created_at: "2026-11-04T08:10:00Z" },
    ] },
    { meal_type: "lunch", totals: totals(), entries: [] },
    { meal_type: "dinner", totals: totals(), entries: [] },
    { meal_type: "snacks", totals: totals(), entries: [] },
  ],
};
