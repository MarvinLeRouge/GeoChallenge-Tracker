import L from 'leaflet'

export type MarkerOptions = {
    color: string
    glyph: string
}

function makeSvg(color: string, label: string): string {
    return `
    <svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 36' width='32' height='48'>
      <path d='M12 2C7 2 3 6 3 11c0 7 9 21 9 21s9-14 9-21c0-5-4-9-9-9z' fill='${color}'/>
      <circle cx='12' cy='11' r='5' fill='white'/>
      <text x='12' y='14' text-anchor='middle' font-size='8' font-family='Arial' fill='black'>${label}</text>
    </svg>
    `
}

export function getMarker({ color, glyph }: MarkerOptions): L.Icon {
    const svg = makeSvg(color, glyph)
    return new L.Icon({
        iconUrl: `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`,
        iconSize: [32, 48],
        iconAnchor: [16, 48],
        popupAnchor: [0, -40],
    })
}
