import axios from "axios";

const BASE = "http://localhost:8000/users";

export const userApi = {
  getAll: () => axios.get(BASE),
  create: (data) => axios.post(BASE + "/", data),
  update: (id, data) => axios.patch(`${BASE}/${id}`, data),
  delete: (id) => axios.delete(`${BASE}/${id}`),
  toggleActive: (id) => axios.patch(`${BASE}/${id}/toggle-active`),
};