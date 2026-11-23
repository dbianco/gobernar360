import { render } from '@testing-library/react'
import { expect, it, vi } from 'vitest'

import { useAuth } from './authContext'
import { useConfirm } from './confirmContext'

function UsesAuth() {
  useAuth()
  return null
}

function UsesConfirm() {
  useConfirm()
  return null
}

it('refuses to be used outside their providers', () => {
  const quiet = vi.spyOn(console, 'error').mockImplementation(() => {})

  expect(() => render(<UsesAuth />)).toThrow('useAuth must be used inside AuthProvider')
  expect(() => render(<UsesConfirm />)).toThrow('useConfirm needs a <ConfirmProvider> above it.')
  quiet.mockRestore()
})
