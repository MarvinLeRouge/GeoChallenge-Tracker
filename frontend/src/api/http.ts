import axios, {
  AxiosError,
  InternalAxiosRequestConfig,
  AxiosHeaders,
} from "axios";
import { useAuthStore } from "@/store/auth";
import { toast } from "vue-sonner";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "/api",
  withCredentials: true,
});

let refreshPromise: Promise<void> | null = null;

/** Logout + redirect to login with reason param (called when session cannot be recovered). */
function handleSessionExpired(): void {
  useAuthStore().logout();
  toast.error("Session expirée", { description: "Veuillez vous reconnecter." });
  // Dynamic import avoids circular dependency: http → router → auth → http
  import("@/router").then(({ default: router }) => {
    if (router.currentRoute.value.name !== "auth/login") {
      router.push({ name: "auth/login" });
    }
  });
}

function setAuthHeader(cfg: InternalAxiosRequestConfig, token: string) {
  // normalise les headers en AxiosHeaders, puis set l’Authorization
  const h =
    cfg.headers instanceof AxiosHeaders
      ? cfg.headers
      : new AxiosHeaders(cfg.headers);
  h.set("Authorization", `Bearer ${token}`);
  cfg.headers = h;
}

// Attach Authorization (restore from sessionStorage if needed)
api.interceptors.request.use((config) => {
  const auth = useAuthStore();

  if (!auth.accessToken) {
    const cached = sessionStorage.getItem("access_token") || "";
    if (cached) auth.accessToken = cached;
  }
  if (auth.accessToken) {
    setAuthHeader(config, auth.accessToken);
  }
  return config;
});

// Lazy refresh on 401, single-flight, then replay
api.interceptors.response.use(
  (res) => res,
  async (error: AxiosError) => {
    const resp = error.response;
    const original = error.config as
      | (InternalAxiosRequestConfig & { _retry?: boolean })
      | undefined;

    if (resp?.status === 401 && original && !original._retry) {
      // don't loop on refresh endpoint
      if (original.url?.includes("/auth/refresh")) {
        handleSessionExpired();
        return Promise.reject(error);
      }

      const auth = useAuthStore();
      original._retry = true;

      if (!refreshPromise) {
        refreshPromise = auth.refresh().finally(() => {
          refreshPromise = null;
        });
      }

      try {
        await refreshPromise;
        if (auth.accessToken) {
          setAuthHeader(original, auth.accessToken);
        }
        return api(original);
      } catch (e) {
        handleSessionExpired();
        return Promise.reject(e);
      }
    }

    return Promise.reject(error);
  },
);

export default api;
