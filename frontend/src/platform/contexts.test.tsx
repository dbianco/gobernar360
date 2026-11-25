import { render } from '@testing-library/react'
import { expect, it, vi } from 'vitest'

import { useAuth } from './authContext'
import { useConfirm } from './confirmContext'
import { useLeafletMap } from './geo/mapContext'

function UsesAuth() {
  useAuth()
  return null
}

function UsesConfirm() {
  useConfirm()
  return null
}

function UsesMap() {
  useLeafletMap()
  return null
}

it('refuses to be used outside their providers', () => {
  const quiet = vi.spyOn(console, 'error').mockImplementation(() => {})

  expect(() => render(<UsesAuth />)).toThrow('useAuth must be used inside AuthProvider')
  expect(() => render(<UsesConfirm />)).toThrow('useConfirm needs a <ConfirmProvider> above it.')
  expect(() => render(<UsesMap />)).toThrow('Map layers must be inside <GeoMap>.')
  quiet.mockRestore()
})
