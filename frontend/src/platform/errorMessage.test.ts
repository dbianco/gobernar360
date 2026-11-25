import { expect, it } from 'vitest'

import { ApiError } from '../api/client'
import { t } from '../test/render'
import { errorMessage } from './errorMessage'

it('has the words for what the server answered', () => {
  expect(errorMessage(new ApiError(409, 'in_use', 'x'))).toBe(t('errors.in_use'))
})

it('speaks in general terms of codes it does not know and of what is not an answer', () => {
  expect(errorMessage(new ApiError(500, 'something_new', 'x'))).toBe(t('errors.generic'))
  expect(errorMessage(new Error('boom'))).toBe(t('errors.generic'))
  expect(errorMessage(null)).toBe(t('errors.generic'))
})
