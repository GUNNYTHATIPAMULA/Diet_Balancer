import { describe, expect, it, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders, apiError } from "./utils";
import { PairDeviceModal } from "../components/dispenser/PairDeviceModal";
import { devicesApi, pairingApi } from "../api/devices";

vi.mock("../api/auth", () => ({ authApi: { me: vi.fn() } }));
vi.mock("../api/devices", () => ({
  devicesApi: { get: vi.fn() },
  pairingApi: { nearby: vi.fn(), claim: vi.fn() },
}));

const NEARBY = { session_id: "s1", hardware_id: "DB-3A7F1C", display_name: "Diet Balancer dispenser 7F1C", firmware_version: "1.1.0",
  local_ip: "192.168.1.50", hardware_info: { calibrated: true }, last_seen_at: new Date().toISOString(), already_yours: false };

beforeEach(() => vi.clearAllMocks());

describe("Pairing a dispenser", () => {
  it("shows dispensers found on the network", async () => {
    pairingApi.nearby.mockResolvedValue([NEARBY]);
    renderWithProviders(<PairDeviceModal open onClose={() => {}} />);
    expect(screen.getByText("Looking for dispensers on your network…")).toBeInTheDocument();
    expect(await screen.findByText("Diet Balancer dispenser 7F1C")).toBeInTheDocument();
  });

  it("connects with the 6-digit code from the dispenser screen (pasted)", async () => {
    pairingApi.nearby.mockResolvedValue([NEARBY]);
    pairingApi.claim.mockResolvedValue({ device: { id: "dev-1", name: "Kitchen dispenser" }, reconnected: false, message: "Connected." });
    devicesApi.get.mockResolvedValue({ id: "dev-1", is_online: false, is_registered: false });
    const onPaired = vi.fn();
    renderWithProviders(<PairDeviceModal open onClose={() => {}} onPaired={onPaired} />);
    await userEvent.click(await screen.findByRole("button", { name: "Connect" }));
    await userEvent.click(screen.getByLabelText("Digit 1"));
    await userEvent.paste("482913");
    await userEvent.click(screen.getByRole("button", { name: "Connect" }));
    await waitFor(() => expect(pairingApi.claim).toHaveBeenCalledWith("482913", "Kitchen dispenser"));
    expect(await screen.findByText("Dispenser connected")).toBeInTheDocument();
    expect(onPaired).toHaveBeenCalled();
  });

  it("requires all six digits and shows a wrong-code error", async () => {
    pairingApi.nearby.mockResolvedValue([]);
    pairingApi.claim.mockRejectedValue(apiError(404, "No dispenser is showing that code. Check the code on its screen and try again."));
    renderWithProviders(<PairDeviceModal open onClose={() => {}} />);
    await userEvent.click(screen.getByRole("button", { name: "I have a code" }));
    await userEvent.type(screen.getByLabelText("Digit 1"), "123");
    await userEvent.click(screen.getByRole("button", { name: "Connect" }));
    expect(await screen.findByText("Enter all 6 digits shown on the dispenser’s screen.")).toBeInTheDocument();
    expect(pairingApi.claim).not.toHaveBeenCalled();
    await userEvent.type(screen.getByLabelText("Digit 4"), "456");
    await userEvent.click(screen.getByRole("button", { name: "Connect" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("No dispenser is showing that code");
  });
});
