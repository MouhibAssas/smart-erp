// axios instance with base URL
import axios from "axios";
import { authService } from "./authService";

const httpClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://localhost:8000",
  headers: {
    "Content-Type": "application/json",
  },
  withCredentials: true, // send cookies (refresh token) on cross-origin requests
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
  async (error) => {
    const originalRequest = error.config;
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      try {
        const { data } = await axios.post(
          (import.meta.env.VITE_API_URL || "http://localhost:8000") + "/auth/refresh",
          {},
          { withCredentials: true }
        );
        authService.saveToken(data.access_token);
        if (data.user) authService.saveUser(data.user);
        originalRequest.headers["Authorization"] = `Bearer ${data.access_token}`;
        return httpClient(originalRequest);
      } catch {
        authService.logout();
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);
 
export default httpClient;