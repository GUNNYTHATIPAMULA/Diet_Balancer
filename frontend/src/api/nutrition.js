import { api, data } from "./client";

export const nutritionApi = {
  summary: (day) => data(api.get("/nutrition/summary", { params: { day } })),
  recommendations: (day, limit = 8) => data(api.get("/nutrition/recommendations", { params: { day, limit } })),
};

export const reportsApi = {
  weekly: (end) => data(api.get("/reports/weekly", { params: { end } })),
  monthly: (year, month) => data(api.get("/reports/monthly", { params: { year, month } })),
};
