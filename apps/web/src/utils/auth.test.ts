import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { getLocalStorage, authHeaders } from './auth'

describe('auth utils', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  afterEach(() => {
    localStorage.clear()
  })

  describe('getLocalStorage', () => {
    it('returns Storage when localStorage is available', () => {
      expect(getLocalStorage()).toBe(localStorage)
    })
  })

  describe('authHeaders', () => {
    it('returns empty object when no API key is set', () => {
      expect(authHeaders()).toEqual({})
    })

    it('returns Authorization header with Bearer token when key is set', () => {
      localStorage.setItem('uar_api_key', 'dev_key')
      expect(authHeaders()).toEqual({ Authorization: 'Bearer dev_key' })
    })

    it('merges with provided init headers', () => {
      localStorage.setItem('uar_api_key', 'dev_key')
      expect(authHeaders({ 'Content-Type': 'application/json' })).toEqual({
        Authorization: 'Bearer dev_key',
        'Content-Type': 'application/json',
      })
    })

    it('Authorization takes precedence over init key', () => {
      localStorage.setItem('uar_api_key', 'dev_key')
      // If init has Authorization it gets overwritten by the real key
      expect(authHeaders({ Authorization: 'old' })).toEqual({
        Authorization: 'Bearer dev_key',
      })
    })
  })
})
