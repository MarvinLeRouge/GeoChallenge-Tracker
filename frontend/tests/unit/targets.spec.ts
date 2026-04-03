import { describe, it, expect, vi, beforeEach } from "vitest";

const mockGet = vi.hoisted(() => vi.fn());
const mockPost = vi.hoisted(() => vi.fn());
const mockToastError = vi.hoisted(() => vi.fn());

vi.mock("@/api/http", () => ({ default: { get: mockGet, post: mockPost } }));
vi.mock("vue-sonner", () => ({ toast: { error: mockToastError } }));

import { useTargets } from "@/composables/useTargets";
import type {
  TargetsRefreshStatus,
  EvaluateAllResult,
  TargetItem,
} from "@/composables/useTargets";

const makeStatus = (needs_refresh = false): TargetsRefreshStatus => ({
  needs_refresh,
  last_not_found_import_at: null,
  last_targets_evaluated_at: null,
});

const makeEvalResult = (): EvaluateAllResult => ({
  ok: true,
  evaluated: 10,
  total_inserted: 5,
  total_updated: 5,
  last_targets_evaluated_at: "2024-01-01T00:00:00",
});

const makeTargetsResponse = (items: Partial<TargetItem>[] = []) => ({
  data: {
    items: items.map((i) => ({
      id: "1",
      cache_id: "c1",
      cache_GC: "GC1",
      matched_tasks_count: 0,
      score: 0,
      ...i,
    })),
    nb_items: items.length,
  },
});

// resetAllMocks also clears queued mockResolvedValueOnce values between tests
beforeEach(() => vi.resetAllMocks());

describe("evaluateAll", () => {
  it("sets evaluating during call and resets after", async () => {
    mockPost.mockResolvedValueOnce({ data: makeEvalResult() });
    const { evaluating, evaluateAll } = useTargets();

    const promise = evaluateAll();
    expect(evaluating.value).toBe(true);
    const result = await promise;
    expect(evaluating.value).toBe(false);
    expect(result).toEqual(makeEvalResult());
  });

  it("resets evaluating even when post fails", async () => {
    mockPost.mockRejectedValueOnce(new Error("fail"));
    const { evaluating, evaluateAll } = useTargets();

    await expect(evaluateAll()).rejects.toThrow("fail");
    expect(evaluating.value).toBe(false);
  });

  it("passes force param", async () => {
    mockPost.mockResolvedValueOnce({ data: makeEvalResult() });
    const { evaluateAll } = useTargets();

    await evaluateAll(true);

    expect(mockPost).toHaveBeenCalledWith(
      "/my/targets/evaluate-all",
      null,
      expect.objectContaining({ params: { force: true } }),
    );
  });
});

describe("fetchTargets", () => {
  it("populates targets and nbItems", async () => {
    mockGet.mockResolvedValueOnce(
      makeTargetsResponse([{ id: "t1" }, { id: "t2" }]),
    );
    const { targets, nbItems, fetchTargets } = useTargets();

    await fetchTargets();

    expect(targets.value).toHaveLength(2);
    expect(nbItems.value).toBe(2);
  });

  it("sets loading true during fetch, false after", async () => {
    mockGet.mockResolvedValueOnce(makeTargetsResponse());
    const { loading, fetchTargets } = useTargets();

    const promise = fetchTargets();
    expect(loading.value).toBe(true);
    await promise;
    expect(loading.value).toBe(false);
  });

  it("adds status_filter param when statusFilter is provided", async () => {
    mockGet.mockResolvedValueOnce(makeTargetsResponse());
    const { fetchTargets } = useTargets();

    await fetchTargets("rejected");

    const params = mockGet.mock.calls[0][1].params;
    expect(params.status_filter).toBe("rejected");
  });

  it("omits status_filter when statusFilter is null", async () => {
    mockGet.mockResolvedValueOnce(makeTargetsResponse());
    const { fetchTargets } = useTargets();

    await fetchTargets(null);

    const params = mockGet.mock.calls[0][1].params;
    expect(params.status_filter).toBeUndefined();
  });

  it("resets loading to false when fetch throws", async () => {
    mockGet.mockRejectedValueOnce(new Error("fail"));
    const { loading, fetchTargets } = useTargets();

    await expect(fetchTargets()).rejects.toThrow("fail");
    expect(loading.value).toBe(false);
  });
});

describe("fetchTargetsNearby", () => {
  it("passes lat, lon, radius_km and sort=distance to the API", async () => {
    mockGet.mockResolvedValueOnce(makeTargetsResponse());
    const { fetchTargetsNearby } = useTargets();

    await fetchTargetsNearby(48.8566, 2.3522, 10);

    const params = mockGet.mock.calls[0][1].params;
    expect(params.lat).toBe(48.8566);
    expect(params.lon).toBe(2.3522);
    expect(params.radius_km).toBe(10);
    expect(params.sort).toBe("distance");
  });

  it("adds status_filter when provided", async () => {
    mockGet.mockResolvedValueOnce(makeTargetsResponse());
    const { fetchTargetsNearby } = useTargets();

    await fetchTargetsNearby(0, 0, 5, "accepted");

    const params = mockGet.mock.calls[0][1].params;
    expect(params.status_filter).toBe("accepted");
  });

  it("resets loading to false when fetch throws", async () => {
    mockGet.mockRejectedValueOnce(new Error("fail"));
    const { loading, fetchTargetsNearby } = useTargets();

    await expect(fetchTargetsNearby(0, 0, 1)).rejects.toThrow("fail");
    expect(loading.value).toBe(false);
  });
});

describe("init", () => {
  it("fetches status and targets when refresh is not needed", async () => {
    mockGet
      .mockResolvedValueOnce({ data: makeStatus(false) })
      .mockResolvedValueOnce(makeTargetsResponse());
    const { init } = useTargets();

    await init();

    expect(mockGet).toHaveBeenCalledTimes(2);
    expect(mockPost).not.toHaveBeenCalled();
  });

  it("evaluates and re-fetches status when refresh is needed", async () => {
    mockGet
      .mockResolvedValueOnce({ data: makeStatus(true) })
      .mockResolvedValueOnce({ data: makeStatus(false) })
      .mockResolvedValueOnce(makeTargetsResponse());
    mockPost.mockResolvedValueOnce({ data: makeEvalResult() });
    const { init } = useTargets();

    await init();

    expect(mockPost).toHaveBeenCalledOnce();
    expect(mockGet).toHaveBeenCalledTimes(3);
  });

  it("calls toast.error when init throws", async () => {
    mockGet.mockRejectedValueOnce(new Error("timeout"));
    const { init } = useTargets();

    await init();

    expect(mockToastError).toHaveBeenCalledOnce();
    expect(mockToastError.mock.calls[0][0]).toContain("targets");
  });
});
