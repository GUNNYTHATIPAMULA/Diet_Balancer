import { api, data } from "./client";

export const devicesApi = {
  list: () => data(api.get("/devices")),
  get: (id) => data(api.get(`/devices/${id}`)),
  create: (name) => data(api.post("/devices", { name })),
  rename: (id, name) => data(api.patch(`/devices/${id}`, { name })),
  remove: (id) => data(api.delete(`/devices/${id}`)),
  rotateToken: (id) => data(api.post(`/devices/${id}/rotate-token`)),
  updateSettings: (id, body) => data(api.put(`/devices/${id}/settings`, body)),
  events: (id, limit = 20) => data(api.get(`/devices/${id}/events`, { params: { limit } })),
  emergencyStop: (id, reason) => data(api.post(`/devices/${id}/emergency-stop`, { reason })),
  resetEmergencyStop: (id) => data(api.post(`/devices/${id}/emergency-stop/reset`)),
  addContainer: (id, body) => data(api.post(`/devices/${id}/containers`, body)),
  updateContainer: (id, containerId, body) => data(api.patch(`/devices/${id}/containers/${containerId}`, body)),
  removeContainer: (id, containerId) => data(api.delete(`/devices/${id}/containers/${containerId}`)),
};

export const dispenserApi = {
  create: (body, idempotencyKey) =>
    data(api.post("/dispenser/commands", body, { headers: { "Idempotency-Key": idempotencyKey } })),
  get: (id) => data(api.get(`/dispenser/commands/${id}`)),
  list: (device_id, limit = 10) => data(api.get("/dispenser/commands", { params: { device_id, limit } })),
  cancel: (id) => data(api.post(`/dispenser/commands/${id}/cancel`)),
  logMeasured: (id, meal_type) => data(api.post(`/dispenser/commands/${id}/log-measured`, { meal_type })),
};

export const pairingApi = {
  nearby: () => data(api.get("/devices/pairing/nearby")),
  claim: (pairing_code, name) => data(api.post("/devices/pairing/claim", { pairing_code, name })),
};
