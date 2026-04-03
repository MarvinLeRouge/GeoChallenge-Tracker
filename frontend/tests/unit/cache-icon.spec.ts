import { describe, it, expect, vi, beforeEach } from "vitest";

class MockIcon {
  options: unknown;
  constructor(options: unknown) {
    this.options = options;
  }
}

vi.mock("leaflet", () => ({
  default: { Icon: MockIcon },
}));

// Fresh module per test to reset the module-level memo Map
beforeEach(() => {
  vi.resetModules();
});

describe("getIconFor", () => {
  it("returns an icon for a known type", async () => {
    const { getIconFor } = await import("@/config/cache-icon");
    const icon = getIconFor("traditional");
    expect(icon).toBeInstanceOf(MockIcon);
  });

  it("falls back to unknown for an unrecognised type", async () => {
    const { getIconFor } = await import("@/config/cache-icon");
    const icon = getIconFor("nonexistent_type");
    expect(icon).toBeInstanceOf(MockIcon);
    const url = (icon as unknown as MockIcon).options as { iconUrl: string };
    // unknown glyph is 'X'
    expect(url.iconUrl).toContain("X");
  });

  it("falls back to unknown for null", async () => {
    const { getIconFor } = await import("@/config/cache-icon");
    const icon = getIconFor(null);
    expect(icon).toBeInstanceOf(MockIcon);
  });

  it("falls back to unknown for undefined", async () => {
    const { getIconFor } = await import("@/config/cache-icon");
    const icon = getIconFor(undefined);
    expect(icon).toBeInstanceOf(MockIcon);
  });

  it("returns the same reference for the same type (memoisation)", async () => {
    const { getIconFor } = await import("@/config/cache-icon");
    const a = getIconFor("mystery");
    const b = getIconFor("mystery");
    expect(a).toBe(b);
  });

  it("is case-insensitive", async () => {
    const { getIconFor } = await import("@/config/cache-icon");
    const lower = getIconFor("traditional");
    const upper = getIconFor("TRADITIONAL");
    expect(lower).toBe(upper);
  });
});

describe("getIcon", () => {
  it("returns an icon for a color/glyph pair", async () => {
    const { getIcon } = await import("@/config/cache-icon");
    const icon = getIcon("#ff0000", "T");
    expect(icon).toBeInstanceOf(MockIcon);
  });

  it("returns the same reference for the same color/glyph (memoisation)", async () => {
    const { getIcon } = await import("@/config/cache-icon");
    const a = getIcon("#ff0000", "T");
    const b = getIcon("#ff0000", "T");
    expect(a).toBe(b);
  });

  it("returns different references for different color/glyph pairs", async () => {
    const { getIcon } = await import("@/config/cache-icon");
    const a = getIcon("#ff0000", "T");
    const b = getIcon("#0000ff", "T");
    expect(a).not.toBe(b);
  });
});
