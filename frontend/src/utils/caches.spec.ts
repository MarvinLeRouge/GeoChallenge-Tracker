import { describe, it, expect } from 'vitest'
import { coalesceTotal } from './caches'

describe('coalesceTotal', () => {
    it('retourne total quand il est défini', () => {
        expect(coalesceTotal([1, 2], 5)).toBe(5)
    })
    it('retourne length des items sinon', () => {
        expect(coalesceTotal([1, 2])).toBe(2)
    })
    it('retourne 0 si rien', () => {
        expect(coalesceTotal(undefined)).toBe(0)
    })
})
