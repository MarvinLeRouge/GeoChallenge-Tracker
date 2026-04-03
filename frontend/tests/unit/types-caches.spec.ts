import { describe, it, expect } from "vitest";
import { isCacheDetailed } from "@/types/caches";
import type { CacheCompact, CacheDetailed } from "@/types/caches";

const base = {
  _id: "507f1f77bcf86cd799439011",
  GC: "GC12345",
  title: "Test Cache",
  type_id: "traditional",
  size_id: "regular",
  difficulty: 2,
  terrain: 2,
  lat: 48.8566,
  lon: 2.3522,
};

const compact: CacheCompact = {
  ...base,
  type: { label: "Traditional", code: "traditional" },
  size: { label: "Regular", code: "regular" },
};

const detailed: CacheDetailed = {
  ...base,
  description_html: "<p>Description</p>",
  placed_at: "2020-01-01T00:00:00",
  loc: { type: "Point", coordinates: [2.3522, 48.8566] },
  elevation: 100,
  country_id: "FR",
  state_id: "75",
  location_more: null,
  attributes: [],
  owner: "TestOwner",
  favorites: 5,
  created_at: "2020-01-01T00:00:00",
  dist_meters: 1000,
};

describe("isCacheDetailed", () => {
  it("returns true for a detailed cache", () => {
    expect(isCacheDetailed(detailed)).toBe(true);
  });

  it("returns false for a compact cache", () => {
    expect(isCacheDetailed(compact)).toBe(false);
  });

  it("returns false when description_html is missing", () => {
    const partial = {
      ...base,
      loc: { type: "Point", coordinates: [0, 0] },
    } as unknown as CacheCompact;
    expect(isCacheDetailed(partial)).toBe(false);
  });

  it("returns false when loc is missing", () => {
    const partial = {
      ...base,
      description_html: "<p>test</p>",
    } as unknown as CacheCompact;
    expect(isCacheDetailed(partial)).toBe(false);
  });

  it("returns true when both description_html and loc are present", () => {
    const both = {
      ...base,
      description_html: "<p>x</p>",
      loc: { type: "Point", coordinates: [0, 0] },
    } as unknown as CacheDetailed;
    expect(isCacheDetailed(both)).toBe(true);
  });
});
