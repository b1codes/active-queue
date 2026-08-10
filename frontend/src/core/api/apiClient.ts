import { useAuthStore } from "@/features/auth/authStore";

const BASE_URL = process.env.EXPO_PUBLIC_API_URL || "http://localhost:8080";

export interface ApiErrorDetail {
  field: string;
  issue: string;
}

export class ApiError extends Error {
  code: string;
  status: number;
  details: ApiErrorDetail[];
  retryAfterSeconds?: number;

  constructor(
    code: string,
    message: string,
    status: number,
    details: ApiErrorDetail[] = [],
    retryAfterSeconds?: number
  ) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.details = details;
    this.retryAfterSeconds = retryAfterSeconds;
  }

  get isRateLimited(): boolean {
    return this.status === 429 || this.code === "RATE_LIMITED";
  }
}


interface ApiResponseEnvelope<T> {
  status: "success" | "error";
  data: T | null;
  error: {
    code: string;
    message: string;
    details?: ApiErrorDetail[];
  } | null;
}

/**
  Core HTTP API client for ActiveQueue mobile frontend.
  - Prepends BASE_URL
  - Injects `Authorization: Bearer <idToken>` header
  - Unwraps response envelopes (`{ status: "success", data: ... }`)
  - Maps SPEC §9.7 error codes to typed `ApiError`
  - Performs **one-shot 401 retry** on `AUTH_TOKEN_EXPIRED` (force refresh via `user.getIdToken(true)`)
 
  No feature module may call `fetch` directly per SPEC §11.2.
 */
export async function apiClient<T>(
  path: string,
  options: RequestInit = {},
  isRetry = false
): Promise<T> {
  const url = path.startsWith("http") ? path : `${BASE_URL}${path}`;
  const { idToken, user } = useAuthStore.getState();

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (idToken) {
    headers["Authorization"] = `Bearer ${idToken}`;
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  const json: ApiResponseEnvelope<T> = await response.json().catch(() => ({
    status: "error" as const,
    data: null,
    error: { code: "INVALID_JSON", message: "Failed to parse response JSON" },
  }));

  // One-shot 401 token refresh retry logic on AUTH_TOKEN_EXPIRED per SPEC §3.1 & §11.2
  if (
    response.status === 401 &&
    json.error?.code === "AUTH_TOKEN_EXPIRED" &&
    !isRetry &&
    user
  ) {
    try {
      // Force token refresh from Firebase Auth
      const freshToken = await user.getIdToken(true);
      useAuthStore.setState({ idToken: freshToken });

      // Retry request EXACTLY ONCE with fresh token (isRetry = true prevents infinite loops)
      return await apiClient<T>(path, options, true);
    } catch {
      // If force token refresh fails, sign out user and throw error
      useAuthStore.getState().signOut();
      throw new ApiError("AUTH_TOKEN_EXPIRED", "Session expired, please sign in again", 401);
    }
  }

  if (!response.ok || json.status === "error" || json.error) {
    const errorBody = json.error || {
      code: "UNKNOWN_ERROR",
      message: `HTTP request failed with status ${response.status}`,
    };

    let retryAfterSeconds: number | undefined;
    const retryAfterHeader = response.headers?.get?.("Retry-After") || response.headers?.get?.("retry-after");
    if (retryAfterHeader) {
      const parsed = parseInt(retryAfterHeader, 10);
      if (!isNaN(parsed)) {
        retryAfterSeconds = parsed;
      }
    }


    throw new ApiError(
      errorBody.code,
      errorBody.message,
      response.status,
      errorBody.details || [],
      retryAfterSeconds
    );
  }


  return json.data as T;
}
