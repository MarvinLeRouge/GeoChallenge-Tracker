import { describe, it, expect, vi } from "vitest";

const MockIcon = vi.hoisted(
  () =>
    class {
      options: unknown;
      constructor(options: unknown) {
        this.options = options;
      }
    },
);

vi.mock("leaflet", () => ({
  default: { Icon: MockIcon },
}));

import { getMarker } from "@/config/markerFactory";

describe("getMarker", () => {
  it("returns a Leaflet Icon instance", () => {
    const icon = getMarker({ color: "#ff0000", glyph: "T" });
    expect(icon).toBeInstanceOf(MockIcon);
  });

  it("encodes the SVG with the given color", () => {
    const icon = getMarker({
      color: "#01884e",
      glyph: "T",
    }) as unknown as InstanceType<typeof MockIcon>;
    const iconUrl = decodeURIComponent(
      (icon.options as { iconUrl: string }).iconUrl,
    );
    expect(iconUrl).toContain("#01884e");
  });

  it("encodes the SVG with the given glyph", () => {
    const icon = getMarker({
      color: "#000",
      glyph: "M",
    }) as unknown as InstanceType<typeof MockIcon>;
    const iconUrl = (icon.options as { iconUrl: string }).iconUrl;
    expect(iconUrl).toContain("M");
  });

  it("sets iconSize to [32, 48]", () => {
    const icon = getMarker({
      color: "#000",
      glyph: "X",
    }) as unknown as InstanceType<typeof MockIcon>;
    expect((icon.options as { iconSize: number[] }).iconSize).toEqual([32, 48]);
  });

  it("sets iconAnchor to [16, 48]", () => {
    const icon = getMarker({
      color: "#000",
      glyph: "X",
    }) as unknown as InstanceType<typeof MockIcon>;
    expect((icon.options as { iconAnchor: number[] }).iconAnchor).toEqual([
      16, 48,
    ]);
  });

  it("sets popupAnchor to [0, -40]", () => {
    const icon = getMarker({
      color: "#000",
      glyph: "X",
    }) as unknown as InstanceType<typeof MockIcon>;
    expect((icon.options as { popupAnchor: number[] }).popupAnchor).toEqual([
      0, -40,
    ]);
  });

  it("produces different iconUrls for different colors", () => {
    const red = getMarker({
      color: "#ff0000",
      glyph: "T",
    }) as unknown as InstanceType<typeof MockIcon>;
    const blue = getMarker({
      color: "#0000ff",
      glyph: "T",
    }) as unknown as InstanceType<typeof MockIcon>;
    const redUrl = (red.options as { iconUrl: string }).iconUrl;
    const blueUrl = (blue.options as { iconUrl: string }).iconUrl;
    expect(redUrl).not.toBe(blueUrl);
  });
});
