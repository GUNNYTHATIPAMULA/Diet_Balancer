import { describe, expect, it, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route } from "react-router-dom";
import { renderWithProviders, apiError } from "./utils";
import LoginPage from "../pages/LoginPage";
import RegisterPage from "../pages/RegisterPage";
import { authApi } from "../api/auth";

vi.mock("../api/auth", () => ({ authApi: { login: vi.fn(), register: vi.fn(), me: vi.fn(), logout: vi.fn() } }));

beforeEach(() => vi.clearAllMocks());

describe("Login page", () => {
  it("validates required fields before calling the API", async () => {
    renderWithProviders(<LoginPage />, { route: "/login", path: "/login" });
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));
    expect(await screen.findByText("Enter your email.")).toBeInTheDocument();
    expect(screen.getByText("Enter your password.")).toBeInTheDocument();
    expect(authApi.login).not.toHaveBeenCalled();
  });

  it("logs in, stores the token and goes to the dashboard", async () => {
    authApi.login.mockResolvedValue({ access_token: "tok", expires_in: 100, user: { full_name: "Asha", has_profile: true } });
    renderWithProviders(<LoginPage />, { route: "/login", path: "/login", extraRoutes: <Route path="/" element={<p>Dashboard</p>} /> });
    await userEvent.type(screen.getByLabelText("Email"), "asha@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "secret123");
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));
    expect(await screen.findByText("Dashboard")).toBeInTheDocument();
    expect(authApi.login).toHaveBeenCalledWith({ email: "asha@example.com", password: "secret123" });
    expect(localStorage.getItem("diet_balancer_token")).toBe("tok");
  });

  it("shows the server's error message on bad credentials", async () => {
    authApi.login.mockRejectedValue(apiError(401, "Email or password is incorrect."));
    renderWithProviders(<LoginPage />, { route: "/login", path: "/login" });
    await userEvent.type(screen.getByLabelText("Email"), "asha@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "wrong1");
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Email or password is incorrect.");
  });
});

describe("Register page", () => {
  it("rejects mismatched and weak passwords", async () => {
    renderWithProviders(<RegisterPage />, { route: "/register", path: "/register" });
    await userEvent.type(screen.getByLabelText("Full name"), "Asha Rao");
    await userEvent.type(screen.getByLabelText("Email"), "asha@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "letters");
    await userEvent.type(screen.getByLabelText("Confirm password"), "different");
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByText("Use at least 8 characters.")).toBeInTheDocument();
    expect(screen.getByText("Passwords do not match.")).toBeInTheDocument();
    expect(authApi.register).not.toHaveBeenCalled();
  });

  it("registers and continues to profile setup", async () => {
    authApi.register.mockResolvedValue({ access_token: "tok", expires_in: 100, user: { full_name: "Asha", has_profile: false } });
    renderWithProviders(<RegisterPage />, { route: "/register", path: "/register", extraRoutes: <Route path="/setup" element={<p>Setup wizard</p>} /> });
    await userEvent.type(screen.getByLabelText("Full name"), "Asha Rao");
    await userEvent.type(screen.getByLabelText("Email"), "asha@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "greenleaf42");
    await userEvent.type(screen.getByLabelText("Confirm password"), "greenleaf42");
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByText("Setup wizard")).toBeInTheDocument();
  });
});
