// src/types/caches.ts
import type { Point } from 'geojson' // npm i -D @types/geojson

// Mini objets renvoyés dans la version compacte
export interface CacheTypeMini {
    label: string
    code: string
}
export interface CacheSizeMini {
    label: string
    code: string
}

// Commun aux deux versions
export interface CacheBase {
    _id: string                // ObjectId stringifié
    GC: string                 // code GC*
    title: string
    type_id: string
    size_id: string
    difficulty: number
    terrain: number
    lat: number
    lon: number
    latitude?: number
    longitude?: number
}

// Version COMPACTE (liste rapide)
export interface CacheCompact extends CacheBase {
    type: CacheTypeMini
    size: CacheSizeMini
}

// Attribut détaillé
export interface CacheAttribute {
    attribute_doc_id: string
    is_positive: boolean
}

// Version DÉTAILLÉE (fiche)
export interface CacheDetailed extends CacheBase {
    description_html: string          // ⚠️ à assainir au rendu (DOMPurify)
    placed_at: string                 // ISO datetime
    loc: Point                        // GeoJSON.Point { type: "Point", coordinates: [lon, lat] }
    elevation: number
    country_id: string
    state_id: string
    location_more: string | null
    attributes: CacheAttribute[]
    owner: string
    favorites: number
    created_at: string                // ISO datetime
    dist_meters: number
}

// Réponse paginée “classique”. Adapte si ton backend expose d’autres méta.
export interface ApiListResponse<T> {
    items: T[]
    total?: number
    page?: number
    nb_pages?: number
    page_size?: number
    next?: string

}

// Type guard pratique si tu reçois un item dont tu ne sais pas s’il est détaillé
export function isCacheDetailed(c: CacheCompact | CacheDetailed): c is CacheDetailed {
    return 'description_html' in c && 'loc' in c
}
