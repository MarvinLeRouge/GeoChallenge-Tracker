// src/composables/useMapPopup.ts
import L from 'leaflet'
import api from '@/api/http'
import DOMPurify from 'dompurify'

// force en string avant sanitize
function sanitAnyType(v: unknown): string {
    return DOMPurify.sanitize(String(v ?? ''))
}

/** Type minimal côté popup (adapte si besoin) */
export type CacheDetails = {
    _id: string
    GC?: string
    title?: string
    type?: { code?: string; name?: string } | null
    size?: { code?: string; name?: string } | null
    difficulty?: number | string | null
    terrain?: number | string | null
}

/** Rendu HTML de la popup (personnalisable) */
function renderCachePopupHtml(d: CacheDetails) {
    const title = sanitAnyType(d?.title)
    const GC = sanitAnyType(d?.GC)
    const type = sanitAnyType(d?.type?.name ?? d?.type?.code ?? '')
    const size = sanitAnyType(d?.size?.name ?? d?.size?.code ?? '')
    const diff = sanitAnyType(d?.difficulty)
    const terr = sanitAnyType(d?.terrain)

    return `
    <div class="p-2 text-sm leading-snug">
      <div class="font-medium">
        ${title || '(Sans titre)'} ${GC ? `<span class="text-xs text-gray-500">(${GC})</span>` : ''}
      </div>
      <div class="mt-1 text-xs text-gray-600">
        ${type ? `Type : ${type}<br/>` : ''}
        ${size ? `Taille : ${size}<br/>` : ''}
        ${(diff || terr) ? `D/T : ${diff ?? '-'} / ${terr ?? '-'}<br/>` : ''}
      </div>
      ${GC
            ? `<div class="mt-2">
               <a class="text-blue-600 underline" target="_blank" rel="noopener"
                  href="https://www.geocaching.com/geocache/${GC}">
                 Ouvrir sur Geocaching
               </a>
             </div>`
            : ''
        }
    </div>
  `
}

export function useMapPopup(options?: {
    /** Personnalise le rendu du HTML si tu veux un autre layout */
    render?: (d: CacheDetails) => string
    /** Texte affiché pendant le fetch */
    loadingHtml?: string
    /** Texte affiché si erreur */
    errorHtml?: string
}) {
    const render = options?.render ?? renderCachePopupHtml
    const loadingHtml = options?.loadingHtml ?? `<div class="p-2 text-sm text-gray-600">Chargement…</div>`
    const errorHtml = options?.errorHtml ?? `<div class="p-2 text-sm text-red-600">Erreur de chargement</div>`

    // Petit cache mémoire (_id → détails) pour éviter les re-fetchs
    const detailsCache = new Map<string, CacheDetails>()

    async function openCachePopup(cacheId: string, marker: L.Marker) {
        // Popup “chargement”
        if (!marker.getPopup()) marker.bindPopup(loadingHtml, { closeButton: true })
        else marker.setPopupContent(loadingHtml)
        marker.openPopup()

        try {
            let d = detailsCache.get(cacheId)
            if (!d) {
                const { data } = await api.get<CacheDetails>(`/caches/by-id/${cacheId}`, {
                    params: { compact: false },
                })
                d = data
                detailsCache.set(cacheId, d)
            }
            const content = render(d)
            marker.setPopupContent(render(d))
        } catch (_err) {
            marker.setPopupContent(errorHtml)
        }
    }

    /** Helper prêt à l’emploi : lie l’handler click au marker */
    function bindPopupToMarker(cacheId: string, marker: L.Marker) {
        marker.bindPopup('', { closeButton: true, autoPan: true })
        marker.off('click') // évite les doublons si rebind
        marker.on('click', (e) => {
            // Important : empêcher la propagation au cluster
            L.DomEvent.stopPropagation(e)
            openCachePopup(cacheId, marker)
        })
    }

    /** Vide le cache si tu changes complètement de zone */
    function clearDetailsCache() {
        detailsCache.clear()
    }

    return {
        openCachePopup,
        bindPopupToMarker,
        clearDetailsCache,
    }
}
