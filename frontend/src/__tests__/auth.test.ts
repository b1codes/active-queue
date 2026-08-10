import { apiClient, ApiError } from "@/features/auth/apiClient";
import { useAuthStore } from "@/features/auth/authStore";

// Mock fetch globally
const globalFetch = jest.fn();
global.fetch = globalFetch;

describe("apiClient", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    useAuthStore.setState({
      user: null,
      idToken: "initial-token-123",
      isAuthenticated: true,
      isLoading: false,
      error: null,
    });
  });

  it("attaches Authorization header with Bearer idToken", async () => {
    globalFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ status: "success", data: { ping: "pong" }, error: null }),
    });

    const result = await apiClient<{ ping: string }>("/api/v1/healthz");

    expect(result).toEqual({ ping: "pong" });
    expect(globalFetch).toHaveBeenCalledWith(
      "http://localhost:8080/api/v1/healthz",
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: "Bearer initial-token-123",
          "Content-Type": "application/json",
        }),
      })
    );
  });

  it("performs one-shot token refresh retry on 401 AUTH_TOKEN_EXPIRED", async () => {
    const mockGetIdToken = jest.fn().mockResolvedValue("fresh-refreshed-token-456");
    useAuthStore.setState({
      user: { getIdToken: mockGetIdToken } as unknown as import("firebase/auth").User,
      idToken: "expired-token-123",
      isAuthenticated: true,
      isLoading: false,
      error: null,
    });

    // First call returns 401 AUTH_TOKEN_EXPIRED
    globalFetch.mockResolvedValueOnce({
      ok: false,
      status: 401,
      json: async () => ({
        status: "error",
        data: null,
        error: { code: "AUTH_TOKEN_EXPIRED", message: "Token expired" },
      }),
    });

    // Second call (retry) returns 200 success
    globalFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        status: "success",
        data: { user: { uid: "u1" } },
        error: null,
      }),
    });

    const data = await apiClient<{ user: { uid: string } }>("/api/v1/users/me");

    expect(mockGetIdToken).toHaveBeenCalledWith(true);
    expect(useAuthStore.getState().idToken).toBe("fresh-refreshed-token-456");
    expect(globalFetch).toHaveBeenCalledTimes(2);
    expect(data).toEqual({ user: { uid: "u1" } });
  });

  it("throws ApiError when response is not ok", async () => {
    globalFetch.mockResolvedValueOnce({
      ok: false,
      status: 403,
      json: async () => ({
        status: "error",
        data: null,
        error: { code: "ACCOUNT_DISABLED", message: "Account disabled" },
      }),
    });

    await expect(apiClient("/api/v1/users/me")).rejects.toThrow(ApiError);
  });
});
