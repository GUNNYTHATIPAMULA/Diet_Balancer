import axios from "axios";

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1").replace(/\/$/, "");
const TOKEN_KEY = "diet_balancer_token";

// The access token lives in localStorage so a page refresh keeps you signed in.
// It is short-lived (12 h by default) and can be revoked with "Sign out everywhere".
export const tokenStore = {
  get: () => {
    try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
  },
  set: (token) => {
    try { localStorage.setItem(TOKEN_KEY, token); } catch { /* storage unavailable */ }
  },
  clear: () => {
    try { localStorage.removeItem(TOKEN_KEY); } catch { /* storage unavailable */ }
  },
};

export const api = axios.create({ baseURL: API_BASE_URL, timeout: 15000 });

api.interceptors.request.use((config) => {
  const token = tokenStore.get();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    const url = error.config?.url || "";
    if (status === 401 && !url.includes("/auth/login") && !url.includes("/auth/change-password")) {
      tokenStore.clear();
      window.dispatchEvent(new CustomEvent("auth:expired"));
    }
    return Promise.reject(error);
  },
);

/** A human-readable message for any API error. */
export function errorMessage(error, fallback = "Something went wrong. Try again.") {
  if (!error) return fallback;
  if (error.response?.data?.error?.message) return error.response.data.error.message;
  if (error.code === "ECONNABORTED") return "The server took too long to respond. Try again.";
  if (error.request && !error.response) return "Can't reach the Diet Balancer server. Check that the backend is running.";
  return fallback;
}

export function errorCode(error) {
  return error?.response?.data?.error?.code;
}

/** Map of field name -> message from a 422 response. */
export function fieldErrors(error) {
  const details = error?.response?.data?.error?.details;
  if (!Array.isArray(details)) return {};
  return Object.fromEntries(details.filter((d) => d.field).map((d) => [d.field, d.message]));
}

export const data = (promise) => promise.then((r) => r.data);
