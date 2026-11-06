import { api, data } from "./client";

export const profileApi = {
  get: () => data(api.get("/profile")),
  save: (body) => data(api.put("/profile", body)),
  updateWeight: (weight_kg) => data(api.patch("/profile/weight", { weight_kg })),
  targets: () => data(api.get("/profile/calorie-target")),
};
