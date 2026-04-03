import { describe, it, expect, vi, beforeEach } from "vitest";

const mockDomCreate = vi.hoisted(() => vi.fn());

vi.mock("leaflet", () => ({
  default: {
    DomUtil: { create: mockDomCreate },
  },
}));

import { installCrosshairPicker } from "@/components/map/crosshairPicker";

const makeOverlay = () => ({ innerHTML: "", remove: vi.fn() });

const makeMap = () => {
  const container = {
    classList: { add: vi.fn(), remove: vi.fn() },
  };
  return {
    getContainer: vi.fn(() => container),
    once: vi.fn(),
    off: vi.fn(),
    container,
  };
};

beforeEach(() => vi.clearAllMocks());

describe("installCrosshairPicker", () => {
  it("creates an overlay element in the map container", () => {
    const overlay = makeOverlay();
    mockDomCreate.mockReturnValueOnce(overlay);
    const map = makeMap();

    installCrosshairPicker(map as never, vi.fn());

    expect(mockDomCreate).toHaveBeenCalledWith(
      "div",
      "leaflet-crosshair-overlay",
      map.container,
    );
    expect(overlay.innerHTML).toContain("<svg");
  });

  it("enable() adds pick-mode class and registers click handler", () => {
    mockDomCreate.mockReturnValueOnce(makeOverlay());
    const map = makeMap();
    const { enable } = installCrosshairPicker(map as never, vi.fn());

    enable();

    expect(map.container.classList.add).toHaveBeenCalledWith("pick-mode");
    expect(map.once).toHaveBeenCalledWith("click", expect.any(Function));
  });

  it("enable() is a no-op when already active", () => {
    mockDomCreate.mockReturnValueOnce(makeOverlay());
    const map = makeMap();
    const { enable } = installCrosshairPicker(map as never, vi.fn());

    enable();
    enable();

    expect(map.once).toHaveBeenCalledOnce();
  });

  it("disable() removes pick-mode class and deregisters click handler", () => {
    mockDomCreate.mockReturnValueOnce(makeOverlay());
    const map = makeMap();
    const { enable, disable } = installCrosshairPicker(map as never, vi.fn());

    enable();
    disable();

    expect(map.container.classList.remove).toHaveBeenCalledWith("pick-mode");
    expect(map.off).toHaveBeenCalledWith("click", expect.any(Function));
  });

  it("disable() is a no-op when not active", () => {
    mockDomCreate.mockReturnValueOnce(makeOverlay());
    const map = makeMap();
    const { disable } = installCrosshairPicker(map as never, vi.fn());

    disable();

    expect(map.container.classList.remove).not.toHaveBeenCalled();
    expect(map.off).not.toHaveBeenCalled();
  });

  it("destroy() disables and removes the overlay", () => {
    const overlay = makeOverlay();
    mockDomCreate.mockReturnValueOnce(overlay);
    const map = makeMap();
    const { enable, destroy } = installCrosshairPicker(map as never, vi.fn());

    enable();
    destroy();

    expect(map.container.classList.remove).toHaveBeenCalledWith("pick-mode");
    expect(overlay.remove).toHaveBeenCalled();
  });

  it("click handler disables picker and calls onPick with latlng", () => {
    mockDomCreate.mockReturnValueOnce(makeOverlay());
    const map = makeMap();
    const onPick = vi.fn();
    const { enable } = installCrosshairPicker(map as never, onPick);

    enable();

    const clickHandler = map.once.mock.calls[0][1];
    const fakeLatLng = { lat: 48.8566, lng: 2.3522 };
    clickHandler({ latlng: fakeLatLng });

    expect(onPick).toHaveBeenCalledWith(fakeLatLng);
    expect(map.container.classList.remove).toHaveBeenCalledWith("pick-mode");
  });
});
