import { api, data } from "./client";

export const mealsApi = {
  create: (body) => data(api.post("/meals", body)),
  daily: (day) => data(api.get("/meals/daily", { params: { day } })),
  weekly: (end) => data(api.get("/meals/weekly", { params: { end } })),
  update: (id, body) => data(api.patch(`/meals/${id}`, body)),
  remove: (id) => data(api.delete(`/meals/${id}`)),
};
