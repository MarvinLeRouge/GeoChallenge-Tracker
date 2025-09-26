import type { FastAPIValidationItem, FastAPIErrorDetail } from '@/types/http'

export const isObject = (v: unknown): v is Record<string, unknown> =>
    typeof v === 'object' && v !== null

export const isValidationItem = (x: unknown): x is FastAPIValidationItem =>
    isObject(x) && (
        ('msg' in x && (x as Record<string, unknown>).msg === undefined || typeof (x as Record<string, unknown>).msg === 'string') ||
        ('loc' in x && Array.isArray((x as Record<string, unknown>).loc))
    )

/** Extrait le "detail" d'une erreur FastAPI (string | array | undefined) */
export const getDetail = (d: unknown): FastAPIErrorDetail => {
    if (!isObject(d)) return undefined
    const raw = (d as Record<string, unknown>).detail
    if (typeof raw === 'string') return raw
    if (Array.isArray(raw) && raw.every(isValidationItem)) return raw

    const msg = (d as Record<string, unknown>).msg
    if (typeof msg === 'string') return msg

    return undefined
}

/** Convertit un detail en texte lisible (pour toasts/logs) */
export const detailToText = (d: FastAPIErrorDetail): string => {
    if (typeof d === 'string') return d
    if (Array.isArray(d)) return d.map(x => x.msg ?? '').filter(Boolean).join('\n')
    return ''
}
