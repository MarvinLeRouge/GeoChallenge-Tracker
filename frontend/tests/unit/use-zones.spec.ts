import { describe, it, expect, vi, beforeEach } from "vitest";

const mockGet = vi.hoisted(() => vi.fn());

vi.mock("@/api/http", () => ({ default: { get: mockGet } }));
vi.mock("@/composables/useApiErrorHandler", () => ({
  useApiErrorHandler: () => ({
    handleApiError: vi.fn().mockReturnValue({ message: "api error" }),
  }),
}));

import { useZones } from "@/composables/useZones";
import type { ZoneListItem, ZoneDetail } from "@/types/zones";

const makeZoneItem = (code: string, count = 5): ZoneListItem => ({
  code,
  name: `Zone ${code}`,
  cache_count: count,
});

const makeZoneDetail = (code: string): ZoneDetail => ({
  code,
  name: `Zone ${code}`,
  cache_count: 3,
  caches: [
    {
      GC: "GC00001",
      title: "Cache A",
      type_code: "traditional",
      difficulty: 2,
      terrain: 2,
    },
  ],
});

beforeEach(() => vi.clearAllMocks());

// ── fetchZones ───────────────────────────────────────────────────────────────

describe("fetchZones", () => {
  it("calls GET /zones with country and level params", async () => {
    mockGet.mockResolvedValueOnce({ data: { items: [] } });
    const { fetchZones } = useZones();

    await fetchZones("FR", 1);

    expect(mockGet).toHaveBeenCalledWith(
      "/zones",
      expect.objectContaining({
        params: expect.objectContaining({ country: "FR", level: 1 }),
      }),
    );
  });

  it("appends type param when a type code is provided", async () => {
    mockGet.mockResolvedValueOnce({ data: { items: [] } });
    const { fetchZones } = useZones();

    await fetchZones("FR", 2, "traditional");

    expect(mockGet).toHaveBeenCalledWith(
      "/zones",
      expect.objectContaining({
        params: expect.objectContaining({ type: "traditional" }),
      }),
    );
  });

  it("does not include type param when undefined", async () => {
    mockGet.mockResolvedValueOnce({ data: { items: [] } });
    const { fetchZones } = useZones();

    await fetchZones("FR", 1, undefined);

    const callParams = mockGet.mock.calls[0][1].params;
    expect(callParams).not.toHaveProperty("type");
  });

  it("returns items on success", async () => {
    const items = [makeZoneItem("FR-84"), makeZoneItem("FR-75")];
    mockGet.mockResolvedValueOnce({ data: { items } });
    const { fetchZones } = useZones();

    const result = await fetchZones("FR", 1);

    expect(result).toEqual(items);
  });

  it("returns empty array on error", async () => {
    mockGet.mockRejectedValueOnce(new Error("network"));
    const { fetchZones } = useZones();

    const result = await fetchZones("FR", 1);

    expect(result).toEqual([]);
  });

  it("sets loading true during call, false after", async () => {
    mockGet.mockResolvedValueOnce({ data: { items: [] } });
    const { loading, fetchZones } = useZones();

    const promise = fetchZones("FR", 1);
    expect(loading.value).toBe(true);
    await promise;
    expect(loading.value).toBe(false);
  });

  it("sets error on failure", async () => {
    mockGet.mockRejectedValueOnce(new Error("fail"));
    const { error, fetchZones } = useZones();

    await fetchZones("FR", 1);

    expect(error.value).toBe("api error");
  });

  it("clears error before each call", async () => {
    mockGet.mockRejectedValueOnce(new Error("fail"));
    const { error, fetchZones } = useZones();
    await fetchZones("FR", 1);
    expect(error.value).toBe("api error");

    mockGet.mockResolvedValueOnce({ data: { items: [] } });
    await fetchZones("FR", 1);
    expect(error.value).toBeNull();
  });
});

// ── fetchZoneDetail ───────────────────────────────────────────────────────────

describe("fetchZoneDetail", () => {
  it("calls GET /zones/{code}", async () => {
    mockGet.mockResolvedValueOnce({ data: makeZoneDetail("FR-84") });
    const { fetchZoneDetail } = useZones();

    await fetchZoneDetail("FR-84");

    expect(mockGet).toHaveBeenCalledWith("/zones/FR-84");
  });

  it("appends type param when provided", async () => {
    mockGet.mockResolvedValueOnce({ data: makeZoneDetail("FR-84") });
    const { fetchZoneDetail } = useZones();

    await fetchZoneDetail("FR-84", "mystery");

    expect(mockGet).toHaveBeenCalledWith("/zones/FR-84?type=mystery");
  });

  it("returns zone detail on success", async () => {
    const detail = makeZoneDetail("FR-84");
    mockGet.mockResolvedValueOnce({ data: detail });
    const { fetchZoneDetail } = useZones();

    const result = await fetchZoneDetail("FR-84");

    expect(result).toEqual(detail);
  });

  it("returns null on error", async () => {
    mockGet.mockRejectedValueOnce(new Error("not found"));
    const { fetchZoneDetail } = useZones();

    const result = await fetchZoneDetail("FR-UNKNOWN");

    expect(result).toBeNull();
  });

  it("sets loading during call", async () => {
    mockGet.mockResolvedValueOnce({ data: makeZoneDetail("FR-84") });
    const { loading, fetchZoneDetail } = useZones();

    const promise = fetchZoneDetail("FR-84");
    expect(loading.value).toBe(true);
    await promise;
    expect(loading.value).toBe(false);
  });
});
