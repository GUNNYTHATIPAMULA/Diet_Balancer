import { describe, expect, it, vi, beforeEach } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders, apiError } from "./utils";
import DispenserPage from "../pages/DispenserPage";
import { containersApi, devicesApi, dispenserApi, mealPlansApi } from "../api/devices";
import { lookupApi } from "../api/foods";

vi.mock("../api/auth", () => ({ authApi: { me: vi.fn() } }));
vi.mock("../api/nutrition", () => ({ nutritionApi: { summary: vi.fn().mockResolvedValue({ remaining: { calories: 1200, protein_g: 60, carbs_g: 150, fat_g: 40 } }) } }));
vi.mock("../api/foods", () => ({ lookupApi: { identify: vi.fn(), importFood: vi.fn() } }));
vi.mock("../api/devices", () => ({
  devicesApi: { list: vi.fn(), get: vi.fn(), events: vi.fn(), emergencyStop: vi.fn(), resetEmergencyStop: vi.fn(), addContainer: vi.fn(), updateContainer: vi.fn(), removeContainer: vi.fn() },
  dispenserApi: { list: vi.fn(), create: vi.fn(), get: vi.fn(), cancel: vi.fn(), logMeasured: vi.fn() },
  pairingApi: { nearby: vi.fn(), claim: vi.fn() },
  containersApi: { assignFood: vi.fn(), setImage: vi.fn(), removeImage: vi.fn() },
  mealPlansApi: { generate: vi.fn(), get: vi.fn(), serve: vi.fn(), stop: vi.fn(), latest: vi.fn() },
}));

const OATS = { id: "oats", name: "Rolled oats (dry)", calories_per_100g: 379, protein_per_100g: 13.2, carbs_per_100g: 67.7, fat_per_100g: 6.5,
  fiber_per_100g: 10.1, categories: ["carbohydrates", "protein", "fiber"], diet_type: "vegan", allergens: ["gluten"], source: "USDA", is_approximate: true, serving_size_g: 40 };

const device = (over = {}) => ({
  id: "dev-1", name: "Kitchen dispenser", token_hint: "ab12", is_online: true, is_registered: true, firmware_version: "1.1.0",
  hardware_info: { servo_count: 2, hx711_ready: true, oled_ready: true, calibrated: true }, ip_address: "192.168.1.50", wifi_rssi: -55,
  device_state: "idle", last_weight_g: 0, last_heartbeat_at: new Date().toISOString(), registered_at: "2026-11-01T00:00:00Z",
  emergency_stop_active: false, active_command_id: null, created_at: "2026-11-01T00:00:00Z", dispense_settings: { inflight_g: 8 },
  containers: [{ id: "c1", slot_number: 1, servo_channel: 0, label: "Container 1", food: OATS, open_angle: 70, closed_angle: 0,
    capacity_g: null, estimated_remaining_g: 640, is_enabled: true, image_url: null, learned_inflight_g: null }],
  ...over,
});

const command = (over = {}) => ({
  id: "cmd-1", device_id: "dev-1", container_id: "c1", container_label: "Container 1", food_item_id: "oats", food_name: "Rolled oats (dry)",
  command_type: "dispense", status: "pending", target_weight_g: 100, dispensed_weight_g: null, last_progress_weight_g: null,
  meal_type: "lunch", log_to_meals: true, cancel_requested: false, error_code: null, error_message: null, meal_entry_id: null,
  created_at: new Date().toISOString(), expires_at: new Date().toISOString(), logs: [], ...over,
});

beforeEach(() => {
  vi.clearAllMocks();
  devicesApi.events.mockResolvedValue([]);
  dispenserApi.list.mockResolvedValue([]);
});

describe("Smart Dispenser page", () => {
  it("shows the device and container cards with food, categories and nutrition", async () => {
    devicesApi.list.mockResolvedValue([device()]);
    renderWithProviders(<DispenserPage />);
    expect(await screen.findByText("Online")).toBeInTheDocument();
    const card = screen.getByRole("heading", { name: "Rolled oats (dry)" }).closest("article");
    expect(within(card).getByText("Carbs")).toBeInTheDocument();
    expect(within(card).getByText("Fiber")).toBeInTheDocument();
    expect(within(card).getByText("379")).toBeInTheDocument();
    expect(screen.queryByText(/640/)).not.toBeInTheDocument(); // no invented stock level
  });

  it("validates a single serve before sending anything", async () => {
    devicesApi.list.mockResolvedValue([device()]);
    renderWithProviders(<DispenserPage />);
    const input = await screen.findByLabelText("Grams of Rolled oats (dry)");
    await userEvent.clear(input);
    await userEvent.type(input, "900");
    await userEvent.click(screen.getByRole("button", { name: "Serve Rolled oats (dry)" }));
    expect(await screen.findByText("Enter 5 to 500 g.")).toBeInTheDocument();
    expect(dispenserApi.create).not.toHaveBeenCalled();
  });

  it("serves one food and shows requested vs measured with tolerance and nutrition", async () => {
    devicesApi.list.mockResolvedValue([device()]);
    dispenserApi.create.mockResolvedValue(command({ status: "completed", dispensed_weight_g: 108, meal_entry_id: "m1", accuracy: "within_tolerance",
      difference_g: 8, difference_percent: 8, tolerance_percent: 10, tolerance_g: 10, nutrition: { calories: 409.3, protein_g: 14.3, carbs_g: 73.1, fat_g: 7.0 } }));
    renderWithProviders(<DispenserPage />);
    const input = await screen.findByLabelText("Grams of Rolled oats (dry)");
    await userEvent.clear(input);
    await userEvent.type(input, "100");
    await userEvent.click(screen.getByRole("button", { name: "Serve Rolled oats (dry)" }));
    await waitFor(() => expect(dispenserApi.create).toHaveBeenCalled());
    const [body, key] = dispenserApi.create.mock.calls[0];
    expect(body).toMatchObject({ device_id: "dev-1", container_id: "c1", target_weight_g: 100, command_type: "dispense" });
    expect(key.length).toBeGreaterThanOrEqual(8);
    const live = await screen.findByRole("region", { name: "Served" });
    expect(within(live).getByText("108 g")).toBeInTheDocument();
    expect(within(live).getByText("+8 g")).toBeInTheDocument();
    expect(within(live).getByText("On target")).toBeInTheDocument();
    expect(within(live).getByText("Added to your food log (from measured weights)")).toBeInTheDocument();
    expect(within(live).getByText("409")).toBeInTheDocument();
  });

  it("reports an overshoot instead of hiding it", async () => {
    devicesApi.list.mockResolvedValue([device()]);
    dispenserApi.create.mockResolvedValue(command({ status: "completed", dispensed_weight_g: 120, accuracy: "over", difference_g: 20,
      difference_percent: 20, tolerance_percent: 10, tolerance_g: 10, nutrition: { calories: 454.8, protein_g: 15.8, carbs_g: 81.2, fat_g: 7.8 } }));
    renderWithProviders(<DispenserPage />);
    const input = await screen.findByLabelText("Grams of Rolled oats (dry)");
    await userEvent.clear(input);
    await userEvent.type(input, "100");
    await userEvent.click(screen.getByRole("button", { name: "Serve Rolled oats (dry)" }));
    expect(await screen.findByText("Over target +20 g (+20%)")).toBeInTheDocument();
  });

  it("generates a meal, lets you adjust portions and serves it", async () => {
    devicesApi.list.mockResolvedValue([device()]);
    const plan = { id: "p1", device_id: "dev-1", status: "proposed", meal_type: "lunch", consumed_on: "2026-11-05", engine: "macro_balance_v1",
      remaining_today: { kcal: 1200, protein: 60, carbs: 150, fat: 40 }, meal_target: { kcal: 400, protein: 20, carbs: 50, fat: 13 },
      items: [{ container_id: "c1", container_label: "Container 1", slot_number: 1, food_id: "oats", food_name: "Rolled oats (dry)",
        categories: ["carbohydrates", "protein", "fiber"], grams: 70, nutrition: { kcal: 265.3, protein: 9.2, carbs: 47.4, fat: 4.6, fiber: 7.1 },
        reasons: ["47.4 g carbohydrates (95% of this meal's carbohydrates)"], command: null }],
      estimated_totals: { kcal: 265.3 }, measured_totals: null, explanation: ["Aimed at 1/3 of what's left today."], skipped: [], created_at: "", served_at: null };
    mealPlansApi.generate.mockResolvedValue(plan);
    mealPlansApi.serve.mockResolvedValue({ ...plan, status: "serving", items: [{ ...plan.items[0], grams: 75, command: command({ target_weight_g: 75 }) }] });
    mealPlansApi.get.mockResolvedValue({ ...plan, status: "serving", items: [{ ...plan.items[0], grams: 75, command: command({ target_weight_g: 75 }) }] });
    renderWithProviders(<DispenserPage />);
    await userEvent.click(await screen.findByRole("button", { name: "Generate My Meal" }));
    expect(await screen.findByText(/95% of this meal's carbohydrates/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "More Rolled oats (dry)" }));
    await userEvent.click(screen.getByRole("button", { name: "Serve Meal" }));
    await waitFor(() => expect(mealPlansApi.serve).toHaveBeenCalledWith("p1", [{ container_id: "c1", grams: 75 }]));
    expect(await screen.findByText("Serving your lunch")).toBeInTheDocument();
  });

  it("configures a container from just a food name, with a confirmation step", async () => {
    devicesApi.list.mockResolvedValue([device({ containers: [] })]);
    lookupApi.identify.mockResolvedValue({ query: "rice", external_provider: null, external_error: null, candidates: [
      { source: "catalogue", food_id: "rice", external_id: null, name: "White rice, raw (dry)", category: "Grains", calories_per_100g: 365,
        protein_per_100g: 7.1, carbs_per_100g: 80, fat_per_100g: 0.7, fiber_per_100g: 1.3, categories: ["carbohydrates"], primary_category: "carbohydrates",
        classification_reasons: ["Carbohydrates supply 90% of energy."], diet_type: "vegan", allergens: [], data_source: "USDA", is_approximate: true,
        dispenser_friendly: true, match: "exact", is_custom: false }] });
    devicesApi.addContainer.mockResolvedValue({ id: "new-c", label: "Container 1" });
    containersApi.assignFood.mockResolvedValue({ id: "new-c", label: "Container 1", food: { name: "White rice, raw (dry)" } });
    renderWithProviders(<DispenserPage />);
    await userEvent.click(await screen.findByRole("button", { name: "Configure container" }));
    await userEvent.type(screen.getByLabelText("What food is in this container?"), "rice");
    expect(await screen.findByText("White rice, raw (dry)")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(screen.getByText("Carbohydrates supply 90% of energy.", { exact: false })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Confirm and save" }));
    await waitFor(() => expect(containersApi.assignFood).toHaveBeenCalledWith("dev-1", "new-c", "rice", "Container 1"));
    expect(devicesApi.addContainer).toHaveBeenCalledWith("dev-1", expect.objectContaining({ slot_number: 1, servo_channel: 0 }));
  });

  it("disables serving when the device is offline", async () => {
    devicesApi.list.mockResolvedValue([device({ is_online: false })]);
    renderWithProviders(<DispenserPage />);
    expect(await screen.findAllByText("Dispenser is offline.")).not.toHaveLength(0);
    expect(screen.getByRole("button", { name: "Serve Rolled oats (dry)" })).toBeDisabled();
  });

  it("shows a server rejection as a toast", async () => {
    devicesApi.list.mockResolvedValue([device()]);
    dispenserApi.create.mockRejectedValue(apiError(409, "The dispenser is busy with another request.", "device_busy"));
    renderWithProviders(<DispenserPage />);
    await userEvent.click(await screen.findByRole("button", { name: "Serve Rolled oats (dry)" }));
    expect(await screen.findByText("The dispenser is busy with another request.")).toBeInTheDocument();
  });

  it("explains how to connect when there is no device", async () => {
    devicesApi.list.mockResolvedValue([]);
    renderWithProviders(<DispenserPage />);
    expect(await screen.findByText("Connect your dispenser")).toBeInTheDocument();
  });
});
