import { describe, expect, it, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders, apiError } from "./utils";
import DispenserPage from "../pages/DispenserPage";
import { devicesApi, dispenserApi } from "../api/devices";

vi.mock("../api/auth", () => ({ authApi: { me: vi.fn() } }));
vi.mock("../api/devices", () => ({
  devicesApi: { list: vi.fn(), events: vi.fn(), emergencyStop: vi.fn(), resetEmergencyStop: vi.fn() },
  dispenserApi: { list: vi.fn(), create: vi.fn(), get: vi.fn(), cancel: vi.fn(), logMeasured: vi.fn() },
  pairingApi: { nearby: vi.fn(), claim: vi.fn() },
}));

const device = (over = {}) => ({
  id: "dev-1", name: "Kitchen dispenser", token_hint: "ab12", is_online: true, is_registered: true, firmware_version: "1.0.0",
  hardware_info: { servo_count: 2, hx711_ready: true, oled_ready: true, calibrated: true }, ip_address: "192.168.1.50", wifi_rssi: -55,
  device_state: "idle", last_weight_g: 0, last_heartbeat_at: new Date().toISOString(), registered_at: "2026-11-01T00:00:00Z",
  emergency_stop_active: false, active_command_id: null, created_at: "2026-11-01T00:00:00Z",
  dispense_settings: { inflight_g: 8 },
  containers: [{ id: "c1", slot_number: 1, servo_channel: 0, label: "Container 1", food: { id: "oats", name: "Rolled oats (dry)", calories_per_100g: 379 },
    open_angle: 90, closed_angle: 0, capacity_g: 1000, estimated_remaining_g: 700, is_enabled: true }],
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
  it("shows device status and containers", async () => {
    devicesApi.list.mockResolvedValue([device()]);
    renderWithProviders(<DispenserPage />);
    expect(await screen.findByText("Online")).toBeInTheDocument();
    expect(screen.getByText("Rolled oats (dry)")).toBeInTheDocument();
    expect(screen.getByText("Ready, calibrated")).toBeInTheDocument();
  });

  it("validates the target before sending anything", async () => {
    devicesApi.list.mockResolvedValue([device()]);
    renderWithProviders(<DispenserPage />);
    await userEvent.type(await screen.findByLabelText("Target grams for Container 1"), "900");
    await userEvent.click(screen.getByRole("button", { name: "Dispense" }));
    expect(await screen.findByText("Enter 5 to 500 g.")).toBeInTheDocument();
    expect(dispenserApi.create).not.toHaveBeenCalled();
  });

  it("sends a command with an idempotency key and shows requested vs measured weight", async () => {
    devicesApi.list.mockResolvedValue([device()]);
    dispenserApi.create.mockResolvedValue(command({ status: "completed", dispensed_weight_g: 97.4, meal_entry_id: "m1" }));
    renderWithProviders(<DispenserPage />);
    await userEvent.type(await screen.findByLabelText("Target grams for Container 1"), "100");
    await userEvent.click(screen.getByRole("button", { name: "Dispense" }));

    await waitFor(() => expect(dispenserApi.create).toHaveBeenCalled());
    const [body, key] = dispenserApi.create.mock.calls[0];
    expect(body).toMatchObject({ device_id: "dev-1", container_id: "c1", target_weight_g: 100, command_type: "dispense", log_to_meals: true });
    expect(typeof key).toBe("string");
    expect(key.length).toBeGreaterThanOrEqual(8);

    expect(await screen.findByText("Requested")).toBeInTheDocument();
    expect(screen.getByText("100 g")).toBeInTheDocument();
    expect(screen.getByText("97.4 g")).toBeInTheDocument();
    expect(screen.getByText(/Added 97.4 g to lunch/)).toBeInTheDocument();
  });

  it("offers to log the measured amount after a failed dispense, but never logs it automatically", async () => {
    devicesApi.list.mockResolvedValue([device()]);
    dispenserApi.create.mockResolvedValue(command({ status: "failed", dispensed_weight_g: 12.3, error_message: "Weight did not increase." }));
    renderWithProviders(<DispenserPage />);
    await userEvent.type(await screen.findByLabelText("Target grams for Container 1"), "100");
    await userEvent.click(screen.getByRole("button", { name: "Dispense" }));
    expect(await screen.findByText("Weight did not increase.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Log measured 12.3 g" })).toBeInTheDocument();
    expect(dispenserApi.logMeasured).not.toHaveBeenCalled();
  });

  it("disables dispensing when the device is offline", async () => {
    devicesApi.list.mockResolvedValue([device({ is_online: false })]);
    renderWithProviders(<DispenserPage />);
    expect(await screen.findByText("Dispenser is offline.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Dispense" })).toBeDisabled();
  });

  it("shows a server rejection as a toast", async () => {
    devicesApi.list.mockResolvedValue([device()]);
    dispenserApi.create.mockRejectedValue(apiError(409, "The dispenser is busy with another request.", "device_busy"));
    renderWithProviders(<DispenserPage />);
    await userEvent.type(await screen.findByLabelText("Target grams for Container 1"), "50");
    await userEvent.click(screen.getByRole("button", { name: "Dispense" }));
    expect(await screen.findByText("The dispenser is busy with another request.")).toBeInTheDocument();
  });

  it("explains how to connect when there is no device", async () => {
    devicesApi.list.mockResolvedValue([]);
    renderWithProviders(<DispenserPage />);
    expect(await screen.findByText("Connect your dispenser")).toBeInTheDocument();
  });
});
