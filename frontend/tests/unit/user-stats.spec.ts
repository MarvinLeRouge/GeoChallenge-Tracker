import { describe, it, expect, vi, beforeEach } from "vitest";

const mockGet = vi.hoisted(() => vi.fn());

vi.mock("@/api/http", () => ({ default: { get: mockGet } }));
vi.mock("@/composables/useApiErrorHandler", () => ({
  useApiErrorHandler: () => ({
    handleApiError: vi.fn().mockReturnValue({ message: "error" }),
  }),
}));

import { useUserStats } from "@/composables/useUserStats";
import type { UserStatsOut } from "@/types/index";

const makeStats = (overrides: Partial<UserStatsOut> = {}): UserStatsOut => ({
  total_caches_found: 100,
  total_challenges: 4,
  completed_challenges: 3,
  active_challenges: 2,
  last_cache_found_at: "2020-01-01T00:00:00",
  caches_by_type: [],
  ...overrides,
});

beforeEach(() => vi.clearAllMocks());

describe("completionRate", () => {
  it("returns 0 when stats is null", () => {
    const { completionRate } = useUserStats();
    expect(completionRate.value).toBe(0);
  });

  it("returns 0 when total_challenges is 0", () => {
    const { stats, completionRate } = useUserStats();
    stats.value = makeStats({ total_challenges: 0, completed_challenges: 0 });
    expect(completionRate.value).toBe(0);
  });

  it("computes the rounded percentage", () => {
    const { stats, completionRate } = useUserStats();
    stats.value = makeStats({ total_challenges: 4, completed_challenges: 3 });
    expect(completionRate.value).toBe(75);
  });

  it("returns 100 when all challenges are completed", () => {
    const { stats, completionRate } = useUserStats();
    stats.value = makeStats({ total_challenges: 5, completed_challenges: 5 });
    expect(completionRate.value).toBe(100);
  });
});

describe("daysSinceLastCache", () => {
  it("returns null when stats is null", () => {
    const { daysSinceLastCache } = useUserStats();
    expect(daysSinceLastCache.value).toBeNull();
  });

  it("returns null when last_cache_found_at is absent", () => {
    const { stats, daysSinceLastCache } = useUserStats();
    stats.value = makeStats({ last_cache_found_at: undefined });
    expect(daysSinceLastCache.value).toBeNull();
  });

  it("returns a positive number of days for a past date", () => {
    const { stats, daysSinceLastCache } = useUserStats();
    stats.value = makeStats({ last_cache_found_at: "2000-01-01T00:00:00" });
    expect(daysSinceLastCache.value).toBeGreaterThan(0);
  });

  it("returns 1 for a cache found today", () => {
    const { stats, daysSinceLastCache } = useUserStats();
    const today = new Date().toISOString();
    stats.value = makeStats({ last_cache_found_at: today });
    expect(daysSinceLastCache.value).toBeGreaterThanOrEqual(0);
    expect(daysSinceLastCache.value).toBeLessThanOrEqual(1);
  });
});

describe("cachesPerActiveChallenge", () => {
  it("returns 0 when stats is null", () => {
    const { cachesPerActiveChallenge } = useUserStats();
    expect(cachesPerActiveChallenge.value).toBe(0);
  });

  it("returns 0 when active_challenges is 0", () => {
    const { stats, cachesPerActiveChallenge } = useUserStats();
    stats.value = makeStats({ active_challenges: 0 });
    expect(cachesPerActiveChallenge.value).toBe(0);
  });

  it("computes the rounded ratio", () => {
    const { stats, cachesPerActiveChallenge } = useUserStats();
    stats.value = makeStats({ total_caches_found: 100, active_challenges: 3 });
    expect(cachesPerActiveChallenge.value).toBe(33);
  });

  it("returns exact value when evenly divisible", () => {
    const { stats, cachesPerActiveChallenge } = useUserStats();
    stats.value = makeStats({ total_caches_found: 100, active_challenges: 2 });
    expect(cachesPerActiveChallenge.value).toBe(50);
  });
});

describe("loadStats", () => {
  it("sets loading true during call, false after", async () => {
    mockGet.mockResolvedValueOnce({ data: makeStats() });
    const { loading, loadStats } = useUserStats();

    const promise = loadStats();
    expect(loading.value).toBe(true);
    await promise;
    expect(loading.value).toBe(false);
  });

  it("populates stats on success", async () => {
    const data = makeStats({ total_caches_found: 42 });
    mockGet.mockResolvedValueOnce({ data });
    const { stats, loadStats } = useUserStats();

    await loadStats();

    expect(stats.value).toEqual(data);
  });

  it("sets error and resets loading on failure", async () => {
    mockGet.mockRejectedValueOnce(new Error("network"));
    const { error, loading, loadStats } = useUserStats();

    await loadStats();

    expect(error.value).toBe("error");
    expect(loading.value).toBe(false);
  });

  it("clears previous error before each call", async () => {
    mockGet.mockRejectedValueOnce(new Error("fail"));
    const { error, loadStats } = useUserStats();
    await loadStats();
    expect(error.value).toBe("error");

    mockGet.mockResolvedValueOnce({ data: makeStats() });
    await loadStats();
    expect(error.value).toBeNull();
  });
});
