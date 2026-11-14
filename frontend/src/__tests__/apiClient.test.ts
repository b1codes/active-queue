import { apiClient, ApiError } from "../core/api/apiClient";

describe("apiClient rate limit error handling", () => {
  beforeEach(() => {
    jest.resetAllMocks();
    global.fetch = jest.fn();
  });

  it("handles HTTP 429 rate limit responses gracefully", async () => {
    const mockHeaders = new Map([["Retry-After", "45"]]);
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: false,
      status: 429,
      headers: {
        get: (key: string) => mockHeaders.get(key) || null,
      },
      json: async () => ({
        status: "error",
        data: null,
        error: {
          code: "RATE_LIMITED",
          message: "Rate limit of 60 requests per minute exceeded. Please try again in 45 seconds.",
        },
      }),
    });

    try {
      await apiClient("/api/v1/activities");
      fail("Expected apiClient to throw ApiError");
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      const apiErr = err as ApiError;
      expect(apiErr.status).toBe(429);
      expect(apiErr.code).toBe("RATE_LIMITED");
      expect(apiErr.isRateLimited).toBe(true);
      expect(apiErr.retryAfterSeconds).toBe(45);
      expect(apiErr.message).toContain("Rate limit of 60 requests per minute exceeded");
    }
  });

  it("identifies rate limiting by code RATE_LIMITED even without status 429", () => {
    const err = new ApiError("RATE_LIMITED", "Too many requests", 400);
    expect(err.isRateLimited).toBe(true);
  });

  it("returns false for isRateLimited on normal errors", () => {
    const err = new ApiError("NOT_FOUND", "Resource not found", 404);
    expect(err.isRateLimited).toBe(false);
    expect(err.retryAfterSeconds).toBeUndefined();
  });
});

describe("apiClient failure mapping", () => {
  const globalFetch = jest.fn();
  beforeEach(() => {
    global.fetch = globalFetch;
  });

  it("maps a rejected fetch to NETWORK_UNAVAILABLE", async () => {
    globalFetch.mockRejectedValueOnce(new TypeError("Network request failed"));
    const err = await apiClient("/x").catch((e: ApiError) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).isNetworkError).toBe(true);
    expect((err as ApiError).status).toBe(0);
  });

  it("parses Retry-After on 429 and flags rate limiting", async () => {
    globalFetch.mockResolvedValueOnce({
      ok: false,
      status: 429,
      headers: { get: (h: string) => (h === "Retry-After" ? "17" : null) },
      json: async () => ({ status: "error", data: null, error: { code: "RATE_LIMITED", message: "slow" } }),
    });
    const err = (await apiClient("/x").catch((e: ApiError) => e)) as ApiError;
    expect(err.isRateLimited).toBe(true);
    expect(err.retryAfterSeconds).toBe(17);
  });

  it("treats a non-JSON error body as UNKNOWN/INVALID_JSON instead of crashing", async () => {
    globalFetch.mockResolvedValueOnce({
      ok: false,
      status: 502,
      headers: { get: () => null },
      json: async () => {
        throw new SyntaxError("Unexpected token <");
      },
    });
    const err = (await apiClient("/x").catch((e: ApiError) => e)) as ApiError;
    expect(err.status).toBe(502);
    expect(err.code).toBe("INVALID_JSON");
  });
});
