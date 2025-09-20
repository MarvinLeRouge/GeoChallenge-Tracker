import L from 'leaflet'
import { CACHE_TYPES } from './cache-types'
import { getMarker } from './markerFactory'

const memo = new Map<string, L.DivIcon>()

export function getIconFor(type: string | undefined | null) {
    const key = (type || 'unknown').toLowerCase()
    if (memo.has(key)) return memo.get(key)!
    const { color, glyph } = CACHE_TYPES[key] ?? CACHE_TYPES.unknown
    const icon = getMarker({ color, glyph })
    memo.set(key, icon)
    return icon
}

export function getIcon(color: string, glyph: string) {
    const k = `${color}|${glyph}`
    if (!memo.has(k)) memo.set(k, getMarker({ color, glyph }))
    return memo.get(k)!
}
