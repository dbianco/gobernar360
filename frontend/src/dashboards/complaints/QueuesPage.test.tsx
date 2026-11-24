import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { expect, it } from 'vitest'

import { t } from '../../test/render'
import { mockApi } from '../../test/server'
import { QueuesPage } from './QueuesPage'
import { LIGHTS, makeClock, makeComplaint, QUEUES, WORKS } from './testData'
import { BASE, renderComplaints } from './testRender'

const label = (key: string, options = {}) => t(`complaints.queues.${key}`, options)

function renderQueues() {
  mockApi('get', `${BASE}/queues`, QUEUES)
  mockApi('get', `${BASE}/queues/${LIGHTS.id}`, [
    makeComplaint({
      id: 'co-7',
      number: 107,
      clock: makeClock({ left_days: -2, status: 'overdue' }),
    }),
    makeComplaint({ id: 'co-1', number: 101 }),
  ])
  const works = mockApi('get', `${BASE}/queues/${WORKS.id}`, [])
  renderComplaints(
    <Routes>
      <Route path="/d/complaints/queues" element={<QueuesPage />} />
    </Routes>,
    { level: 'viewer', route: '/d/complaints/queues' },
  )
  return { works }
}

it('shows every area with its counts and the first area queue, closest deadline first', async () => {
  renderQueues()

  const lights = within(await screen.findByRole('row', { name: /Alumbrado Público/ }))
  expect(
    lights
      .getAllByRole('cell')
      .map((cell) => cell.textContent)
      .slice(0, 5),
  ).toEqual(['Alumbrado Público', '4', '1', '2', '1'])
  const queue = await screen.findByRole('table', { name: label('title', { name: LIGHTS.name }) })
  const numbers = within(queue)
    .getAllByRole('link')
    .map((link) => link.textContent)
  expect(numbers).toEqual(['107', '101'])
  expect(within(queue).getByText('Vencido por 2 días hábiles')).toBeInTheDocument()
})

it('switches to another area queue', async () => {
  const { works } = renderQueues()
  const user = userEvent.setup()

  await user.click(
    await screen.findByRole('button', { name: label('showNamed', { name: WORKS.name }) }),
  )

  expect(
    await screen.findByRole('heading', { name: label('title', { name: WORKS.name }) }),
  ).toBeInTheDocument()
  expect(await screen.findByText(label('empty'))).toBeInTheDocument()
  expect(works).toHaveLength(1)
})
