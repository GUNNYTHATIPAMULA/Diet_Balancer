import { describe, expect, it, vi, beforeEach } from "vitest";
import { screen, within } from "@testing-library/react";
import { renderWithProviders, SUMMARY, apiError } from "./utils";
import OverviewPage from "../pages/OverviewPage";
import { nutritionApi } from "../api/nutrition";
import { mealsApi } from "../api/meals";
import { devicesApi } from "../api/devices";
import { CalorieRing } from "../components/CalorieRing";
import { render } from "@testing-library/react";

vi.mock("../api/auth", () => ({ authApi: { me: vi.fn().mockResolvedValue({ full_name: "Asha Rao", has_profile: true }) } }));
vi.mock("../api/nutrition", () => ({ nutritionApi: { summary: vi.fn(), recommendations: vi.fn() } }));
vi.mock("../api/meals", () => ({ mealsApi: { weekly: vi.fn(), remove: vi.fn() } }));
vi.mock("../api/devices", () => ({ devicesApi: { list: vi.fn() } }));

const week = { start_date: "2026-10-29", end_date: "2026-11-04", days: Array.from({ length: 7 }, (_, i) => ({ date: `2026-11-0${i + 1 > 4 ? 4 : i + 1}`, calories: 1500, protein_g: 60, carbs_g: 200, fat_g: 40, fiber_g: 20, entries: 3 })) };

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.setItem("diet_balancer_token", "tok");
});

describe("Overview dashboard", () => {
  it("renders targets, meals, dispenser status and suggestions from the API", async () => {
    nutritionApi.summary.mockResolvedValue(SUMMARY);
    nutritionApi.recommendations.mockResolvedValue({ message: "Protein first.", items: [
      { food_id: "p", food_name: "Paneer", suggested_quantity_g: 50, calories: 133, protein_g: 9.2 }] });
    mealsApi.weekly.mockResolvedValue(week);
    devicesApi.list.mockResolvedValue([{ id: "d", name: "Kitchen dispenser", is_online: true, last_heartbeat_at: new Date().toISOString(), last_weight_g: 12.5 }]);

    renderWithProviders(<OverviewPage />);
    expect(await screen.findByText("kcal left today")).toBeInTheDocument();
    expect(screen.getAllByText("1,200")).toHaveLength(2); // ring centre and "Remaining" tile
    const breakfast = screen.getByRole("region", { name: "Breakfast" });
    expect(within(breakfast).getByText("Idli")).toBeInTheDocument();
    expect(within(breakfast).getByText("Measured")).toBeInTheDocument(); // dispenser entry is flagged
    expect(screen.getByText("Paneer")).toBeInTheDocument();
    expect(screen.getByText("Kitchen dispenser")).toBeInTheDocument();
    expect(screen.getByText(/Daily target 1,730 kcal/)).toBeInTheDocument();
  });

  it("shows a loading skeleton, then an error with retry", async () => {
    nutritionApi.summary.mockRejectedValue(apiError(500, "Something went wrong on the server."));
    nutritionApi.recommendations.mockResolvedValue({ items: [] });
    mealsApi.weekly.mockResolvedValue(week);
    devicesApi.list.mockResolvedValue([]);
    renderWithProviders(<OverviewPage />);
    expect(screen.getByLabelText("Loading")).toBeInTheDocument();
    expect(await screen.findByText("Something went wrong on the server.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });
});

describe("CalorieRing", () => {
  it("shows kcal over target in alert wording", () => {
    render(<CalorieRing consumed={2100} target={1800} />);
    expect(screen.getByText("300")).toBeInTheDocument();
    expect(screen.getByText("kcal over target")).toBeInTheDocument();
  });
});
