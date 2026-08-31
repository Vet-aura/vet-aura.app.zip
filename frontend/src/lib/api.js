import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({
  baseURL: API,
  timeout: 120000,
  withCredentials: true,
});

const stored = typeof window !== "undefined" ? localStorage.getItem("vetaura_token") : null;
if (stored) api.defaults.headers.common["Authorization"] = `Bearer ${stored}`;

export function setAuthToken(token) {
  if (token) api.defaults.headers.common["Authorization"] = `Bearer ${token}`;
  else delete api.defaults.headers.common["Authorization"];
}
