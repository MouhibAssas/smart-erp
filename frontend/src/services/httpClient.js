// axios instance with base URL
import axios from "axios";
import { authService } from "./authService";

const httpClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://localhost:8000",
  headers: {
    "Content-Type": "application/json",
  },
});
// Attach token to every request
httpClient.interceptors.request.use((config) => {
  const token = authService.getToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});
 
// On 401 → clear token and redirect to login
httpClient.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      authService.clear();
      window.location.href = "/login";
    }
    return Promise.reject(err);
  }
);
 
export default httpClient;