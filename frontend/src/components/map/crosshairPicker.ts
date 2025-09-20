// components/map/crosshairPicker.ts
import L from "leaflet";

export type CrosshairPicker = {
  enable: () => void;
  disable: () => void;
  destroy: () => void;
};

export function installCrosshairPicker(
  map: L.Map,
  onPick: (latlng: L.LatLng) => void,
): CrosshairPicker {
  // Réticule centré ajouté dans le container de la map
  const overlay = L.DomUtil.create("div", "leaflet-crosshair-overlay", map.getContainer());
  overlay.innerHTML = `
    <svg viewBox="0 0 24 24" width="36" height="36" aria-hidden="true">
      <circle cx="12" cy="12" r="5" fill="none" stroke="currentColor" stroke-width="2"/>
      <line x1="12" y1="2"  x2="12" y2="6"  stroke="currentColor" stroke-width="2"/>
      <line x1="12" y1="18" x2="12" y2="22" stroke="currentColor" stroke-width="2"/>
      <line x1="2"  y1="12" x2="6"  y2="12" stroke="currentColor" stroke-width="2"/>
      <line x1="18" y1="12" x2="22" y2="12" stroke="currentColor" stroke-width="2"/>
    </svg>
  `;

  let active = false;

  const handlePick = (e: L.LeafletMouseEvent) => {
    onPick(e.latlng);       // ou map.getCenter() si tu préfères le centre
    disable();
  };

  function enable() {
    if (active) return;
    active = true;
    map.getContainer().classList.add("pick-mode");
    map.once("click", handlePick);
  }

  function disable() {
    if (!active) return;
    active = false;
    map.getContainer().classList.remove("pick-mode");
    map.off("click", handlePick);
  }

  function destroy() {
    disable();
    overlay.remove();
  }

  return { enable, disable, destroy };
}
