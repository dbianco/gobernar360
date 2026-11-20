import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { expect, it } from 'vitest'

import { makeMe } from '../../test/fixtures'
import { renderApp, t } from '../../test/render'
import { mockApi } from '../../test/server'
import { RequirementLinkForm } from './RequirementLinkForm'
import { FORM } from './testData'
import type { Requirement } from './types'

/** The form opened before the list of requirements has arrived. */
function LateOptions() {
  const [available, setAvailable] = useState<Requirement[]>([])
  return (
    <>
      <button onClick={() => setAvailable([FORM])}>options arrive</button>
      <RequirementLinkForm procedureId="pr-1" available={available} onDone={() => {}} />
    </>
  )
}

it('adds the requirement shown as selected even when the options arrived late', async () => {
  const requests = mockApi('post', '/dashboards/procedures/procedures/pr-1/requirements', {}, 201)
  renderApp(<LateOptions />, { me: makeMe({ dashboards: { procedures: 'editor' } }) })
  const user = userEvent.setup()

  await user.click(screen.getByRole('button', { name: 'options arrive' }))
  await user.click(await screen.findByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toMatchObject({ requirement_id: FORM.id })
})
