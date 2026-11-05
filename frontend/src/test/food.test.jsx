import { describe, expect, it, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "./utils";
import { AddMealModal } from "../components/AddMealModal";
import { foodsApi } from "../api/foods";
import { mealsApi } from "../api/meals";

vi.mock("../api/auth", () => ({ authApi: { me: vi.fn() } }));
vi.mock("../api/foods", () => ({ foodsApi: { search: vi.fn() } }));
vi.mock("../api/meals", () => ({ mealsApi: { create: vi.fn(), update: vi.fn() } }));

const RICE = { id: "rice", name: "White rice, cooked", category: "Grains", calories_per_100g: 130, protein_per_100g: 2.7, carbs_per_100g: 28.2,
  fat_per_100g: 0.3, fiber_per_100g: 0.4, serving_unit: "1 cup", serving_size_g: 160, is_custom: false };

beforeEach(() => vi.clearAllMocks());

describe("Food search and meal logging", () => {
  it("searches, previews scaled nutrition and logs the meal", async () => {
    foodsApi.search.mockResolvedValue({ items: [RICE], total: 1 });
    mealsApi.create.mockResolvedValue({});
    const onSaved = vi.fn();
    const onClose = vi.fn();
    renderWithProviders(<AddMealModal open day="2026-11-04" defaultMeal="lunch" onSaved={onSaved} onClose={onClose} />);

    await userEvent.type(screen.getByLabelText("Search foods"), "rice");
    const option = await screen.findByRole("option", { name: /White rice, cooked/ });
    await userEvent.click(option);

    const qty = screen.getByLabelText("Quantity");
    await userEvent.clear(qty);
    await userEvent.type(qty, "150");
    expect(screen.getByText("195")).toBeInTheDocument(); // 130 kcal x 150 g / 100

    await userEvent.click(screen.getByRole("button", { name: "Add to log" }));
    await waitFor(() => expect(mealsApi.create).toHaveBeenCalledWith({ food_item_id: "rice", meal_type: "lunch", quantity_g: 150, consumed_on: "2026-11-04" }));
    expect(onSaved).toHaveBeenCalled();
    expect(onClose).toHaveBeenCalled();
  });

  it("tells the user when nothing matches", async () => {
    foodsApi.search.mockResolvedValue({ items: [], total: 0 });
    renderWithProviders(<AddMealModal open day="2026-11-04" onClose={() => {}} />);
    await userEvent.type(screen.getByLabelText("Search foods"), "pizza");
    expect(await screen.findByText(/No foods match/)).toBeInTheDocument();
  });

  it("requires a valid quantity", async () => {
    renderWithProviders(<AddMealModal open day="2026-11-04" initialFood={RICE} onClose={() => {}} />);
    const qty = screen.getByLabelText("Quantity");
    await userEvent.clear(qty);
    await userEvent.click(screen.getByRole("button", { name: "Add to log" }));
    expect(await screen.findByText("Enter a quantity between 1 and 5000 grams.")).toBeInTheDocument();
    expect(mealsApi.create).not.toHaveBeenCalled();
  });
});
