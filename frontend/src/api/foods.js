import { api, data } from "./client";

export const foodsApi = {
  list: (params) => data(api.get("/foods", { params })),
  search: (q, limit = 20) => data(api.get("/foods/search", { params: { q, limit } })),
  categories: () => data(api.get("/foods/categories")),
  create: (body) => data(api.post("/foods", body)),
  remove: (id) => data(api.delete(`/foods/${id}`)),
};

export const lookupApi = {
  identify: (q) => data(api.get("/foods/identify", { params: { q } })),
  importFood: (external_id, diet_type, allergens) =>
    data(api.post("/foods/import", { source: "usda_fdc", external_id, diet_type, allergens })),
};
