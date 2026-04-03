import { describe, it, expect, vi, beforeEach } from "vitest";

const mockGet = vi.hoisted(() => vi.fn());
const mockStopPropagation = vi.hoisted(() => vi.fn());

vi.mock("@/api/http", () => ({ default: { get: mockGet } }));
vi.mock("dompurify", () => ({
  default: { sanitize: vi.fn((s: string) => s) },
}));
vi.mock("leaflet", () => ({
  default: { DomEvent: { stopPropagation: mockStopPropagation } },
}));

import { useMapPopup } from "@/composables/useMapPopup";
import type { CacheDetails } from "@/composables/useMapPopup";

const makeMarker = (hasPopup = false) => ({
  getPopup: vi.fn().mockReturnValue(hasPopup ? {} : null),
  bindPopup: vi.fn(),
  setPopupContent: vi.fn(),
  openPopup: vi.fn(),
  off: vi.fn(),
  on: vi.fn(),
});

const makeCache = (overrides: Partial<CacheDetails> = {}): CacheDetails => ({
  _id: "abc123",
  GC: "GC12345",
  title: "Test Cache",
  type: { code: "traditional", name: "Traditional" },
  size: { code: "regular", name: "Regular" },
  difficulty: 2,
  terrain: 2,
  ...overrides,
});

beforeEach(() => vi.clearAllMocks());

describe("openCachePopup", () => {
  it("binds loading popup then fetches and sets final content", async () => {
    const cache = makeCache();
    mockGet.mockResolvedValueOnce({ data: cache });
    const marker = makeMarker();
    const { openCachePopup } = useMapPopup();

    await openCachePopup("abc123", marker as never);

    expect(marker.bindPopup).toHaveBeenCalledOnce();
    expect(marker.openPopup).toHaveBeenCalledOnce();
    expect(marker.setPopupContent).toHaveBeenCalledOnce();
    const html: string = marker.setPopupContent.mock.calls[0][0];
    expect(html).toContain("Test Cache");
    expect(html).toContain("GC12345");
  });

  it("uses setPopupContent for loading when popup already exists", async () => {
    mockGet.mockResolvedValueOnce({ data: makeCache() });
    const marker = makeMarker(true);
    const { openCachePopup } = useMapPopup();

    await openCachePopup("abc123", marker as never);

    expect(marker.bindPopup).not.toHaveBeenCalled();
    // setPopupContent called twice: once for loading, once for final
    expect(marker.setPopupContent).toHaveBeenCalledTimes(2);
  });

  it("shows error HTML when fetch fails", async () => {
    mockGet.mockRejectedValueOnce(new Error("Network error"));
    const marker = makeMarker();
    const { openCachePopup } = useMapPopup();

    await openCachePopup("abc123", marker as never);

    const html: string = marker.setPopupContent.mock.calls[0][0];
    expect(html).toContain("Erreur");
  });

  it("uses custom errorHtml when provided", async () => {
    mockGet.mockRejectedValueOnce(new Error("fail"));
    const marker = makeMarker();
    const { openCachePopup } = useMapPopup({
      errorHtml: "<b>Custom error</b>",
    });

    await openCachePopup("abc123", marker as never);

    const html: string = marker.setPopupContent.mock.calls[0][0];
    expect(html).toBe("<b>Custom error</b>");
  });

  it("uses custom loadingHtml when provided", async () => {
    mockGet.mockResolvedValueOnce({ data: makeCache() });
    const marker = makeMarker();
    const { openCachePopup } = useMapPopup({ loadingHtml: "<i>Loading…</i>" });

    const promise = openCachePopup("abc123", marker as never);
    // bindPopup is called with loadingHtml on first open
    expect(marker.bindPopup).toHaveBeenCalledWith(
      "<i>Loading…</i>",
      expect.any(Object),
    );
    await promise;
  });

  it("does not re-fetch on second call for the same id (memo)", async () => {
    mockGet.mockResolvedValue({ data: makeCache() });
    const { openCachePopup } = useMapPopup();
    const marker = makeMarker();

    await openCachePopup("abc123", marker as never);
    await openCachePopup("abc123", makeMarker() as never);

    expect(mockGet).toHaveBeenCalledOnce();
  });

  it("uses custom render function when provided", async () => {
    mockGet.mockResolvedValueOnce({ data: makeCache() });
    const marker = makeMarker();
    const { openCachePopup } = useMapPopup({
      render: () => "<span>custom</span>",
    });

    await openCachePopup("abc123", marker as never);

    const html: string = marker.setPopupContent.mock.calls[0][0];
    expect(html).toBe("<span>custom</span>");
  });
});

describe("clearDetailsCache", () => {
  it("forces a re-fetch after clearing", async () => {
    mockGet.mockResolvedValue({ data: makeCache() });
    const { openCachePopup, clearDetailsCache } = useMapPopup();
    const marker = makeMarker();

    await openCachePopup("abc123", marker as never);
    clearDetailsCache();
    await openCachePopup("abc123", makeMarker() as never);

    expect(mockGet).toHaveBeenCalledTimes(2);
  });
});

describe("bindPopupToMarker", () => {
  it("binds an empty popup and registers a click handler", () => {
    const marker = makeMarker();
    const { bindPopupToMarker } = useMapPopup();

    bindPopupToMarker("abc123", marker as never);

    expect(marker.bindPopup).toHaveBeenCalledWith("", expect.any(Object));
    expect(marker.off).toHaveBeenCalledWith("click");
    expect(marker.on).toHaveBeenCalledWith("click", expect.any(Function));
  });

  it("click handler calls stopPropagation and opens popup", () => {
    mockGet.mockResolvedValue({ data: makeCache() });
    const marker = makeMarker();
    const { bindPopupToMarker } = useMapPopup();

    bindPopupToMarker("abc123", marker as never);

    const clickHandler = marker.on.mock.calls[0][1];
    const fakeEvent = {};
    clickHandler(fakeEvent);

    expect(mockStopPropagation).toHaveBeenCalledWith(fakeEvent);
  });
});

describe("renderCachePopupHtml — no GC branch", () => {
  it("omits geocaching link when GC is absent", async () => {
    const cache = makeCache({ GC: undefined });
    mockGet.mockResolvedValueOnce({ data: cache });
    const marker = makeMarker();
    const { openCachePopup } = useMapPopup();

    await openCachePopup("abc123", marker as never);

    const html: string = marker.setPopupContent.mock.calls[0][0];
    expect(html).not.toContain("geocaching.com");
  });
});
