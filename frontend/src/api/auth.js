import { api, data } from "./client";

export const authApi = {
  register: (body) => data(api.post("/auth/register", body)),
  login: (body) => data(api.post("/auth/login", body)),
  me: () => data(api.get("/auth/me")),
  updateMe: (body) => data(api.patch("/auth/me", body)),
  changePassword: (body) => data(api.post("/auth/change-password", body)),
  logout: () => data(api.post("/auth/logout")),
  logoutAll: () => data(api.post("/auth/logout-all")),
};
