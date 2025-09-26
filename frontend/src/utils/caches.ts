// src/utils/caches.ts
export function coalesceTotal<T>(items: T[] | undefined, total?: number): number {
    return typeof total === 'number' ? total : (Array.isArray(items) ? items.length : 0)
}
