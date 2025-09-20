import L from 'leaflet'

export type MarkerOptions = {
    color: string
    glyph: string
    size?: number   // px
    weight?: number // bordure px
}

export function markerFactory({ color, glyph, size = 28, weight = 3 }: MarkerOptions): L.DivIcon {
    const html =
        `<div class="gc-pin" style="--c:${color};--s:${size}px;--w:${weight}px"><span>${glyph}</span></div>`
    return L.divIcon({
        className: 'gc-pin-wrap',
        html,
        iconSize: [size, size],
        iconAnchor: [size / 2, size],
        popupAnchor: [0, -size * 0.85],
    })
}
