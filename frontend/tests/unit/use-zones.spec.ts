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
  cache_count: 5,
  type_counts: [
    { type_code: "traditional", type_name: "Traditional", count: 5 },
    { type_code: "mystery", type_name: "Mystery", count: 0 },
  ],
});

beforeEach(() => vi.clearAllMocks());

// ── fetchZones ───────────────────────────────────────────────────────────────

describe("fetchZones", () => {
  it("calls GET /zones with level param", async () => {
    mockGet.mockResolvedValueOnce({ data: { items: [] } });
    const { fetchZones } = useZones();

    await fetchZones(0);

    expect(mockGet).toHaveBeenCalledWith(
      "/zones",
      expect.objectContaining({
        params: expect.objectContaining({ level: 0 }),
      }),
    );
  });

  it("does not include country param when omitted", async () => {
    mockGet.mockResolvedValueOnce({ data: { items: [] } });
    const { fetchZones } = useZones();

    await fetchZones(0);

    const callParams = mockGet.mock.calls[0][1].params;
    expect(callParams).not.toHaveProperty("country");
  });

  it("includes country param when provided", async () => {
    mockGet.mockResolvedValueOnce({ data: { items: [] } });
    const { fetchZones } = useZones();

    await fetchZones(1, "FR");

    expect(mockGet).toHaveBeenCalledWith(
      "/zones",
      expect.objectContaining({
        params: expect.objectContaining({ level: 1, country: "FR" }),
      }),
    );
  });

  it("appends type param as an array when type codes are provided", async () => {
    mockGet.mockResolvedValueOnce({ data: { items: [] } });
    const { fetchZones } = useZones();

    await fetchZones(2, "FR", ["traditional", "mystery"]);

    expect(mockGet).toHaveBeenCalledWith(
      "/zones",
      expect.objectContaining({
        params: expect.objectContaining({
          type: ["traditional", "mystery"],
        }),
      }),
    );
  });

  it("does not include type param when empty or undefined", async () => {
    mockGet.mockResolvedValueOnce({ data: { items: [] } });
    const { fetchZones } = useZones();

    await fetchZones(1, "FR", []);

    const callParams = mockGet.mock.calls[0][1].params;
    expect(callParams).not.toHaveProperty("type");
  });

  it("returns items on success", async () => {
    const items = [makeZoneItem("FR-84"), makeZoneItem("FR-75")];
    mockGet.mockResolvedValueOnce({ data: { items } });
    const { fetchZones } = useZones();

    const result = await fetchZones(1, "FR");

    expect(result).toEqual(items);
  });

  it("returns empty array on error", async () => {
    mockGet.mockRejectedValueOnce(new Error("network"));
    const { fetchZones } = useZones();

    const result = await fetchZones(1, "FR");

    expect(result).toEqual([]);
  });

  it("sets loading true during call, false after", async () => {
    mockGet.mockResolvedValueOnce({ data: { items: [] } });
    const { loading, fetchZones } = useZones();

    const promise = fetchZones(1, "FR");
    expect(loading.value).toBe(true);
    await promise;
    expect(loading.value).toBe(false);
  });

  it("sets error on failure", async () => {
    mockGet.mockRejectedValueOnce(new Error("fail"));
    const { error, fetchZones } = useZones();

    await fetchZones(1, "FR");

    expect(error.value).toBe("api error");
  });

  it("clears error before each call", async () => {
    mockGet.mockRejectedValueOnce(new Error("fail"));
    const { error, fetchZones } = useZones();
    await fetchZones(1, "FR");
    expect(error.value).toBe("api error");

    mockGet.mockResolvedValueOnce({ data: { items: [] } });
    await fetchZones(1, "FR");
    expect(error.value).toBeNull();
  });
});

// ── fetchZoneDetail ───────────────────────────────────────────────────────────

describe("fetchZoneDetail", () => {
  it("calls GET /zones/{code} without params when level is omitted", async () => {
    mockGet.mockResolvedValueOnce({ data: makeZoneDetail("FR-84") });
    const { fetchZoneDetail } = useZones();

    await fetchZoneDetail("FR-84");

    expect(mockGet).toHaveBeenCalledWith("/zones/FR-84", { params: {} });
  });

  it("appends level param when provided", async () => {
    mockGet.mockResolvedValueOnce({ data: makeZoneDetail("FR-84") });
    const { fetchZoneDetail } = useZones();

    await fetchZoneDetail("FR-84", 1);

    expect(mockGet).toHaveBeenCalledWith("/zones/FR-84", {
      params: { level: 1 },
    });
  });

  it("returns zone detail with type_counts on success", async () => {
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

  it("sets error on failure", async () => {
    mockGet.mockRejectedValueOnce(new Error("fail"));
    const { error, fetchZoneDetail } = useZones();

    await fetchZoneDetail("FR-84");

    expect(error.value).toBe("api error");
  });
});
