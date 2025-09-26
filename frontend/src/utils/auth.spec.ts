import { describe, it, expect } from 'vitest'
import type { ProfileBaseApi } from '@/types/auth'
import { mapProfileBase } from './auth'


describe('mapProfileBase', () => {
    it('renomme _id en id et préserve les champs', () => {
        const api: ProfileBaseApi = {
            _id: '689ee343223844287350eed9',
            email: 'admin@geochallenge.app',
            username: 'MarvinLeRougeFamily',
            role: 'admin',
        }
        const mapped = mapProfileBase(api)
        expect(mapped).toEqual({
            id: '689ee343223844287350eed9',
            email: 'admin@geochallenge.app',
            username: 'MarvinLeRougeFamily',
            role: 'admin',
        })
    })
})
