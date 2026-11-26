import { screen } from '@testing-library/react'
import { expect, it } from 'vitest'

import { t } from '../../test/render'
import { ComplaintForm } from './ComplaintForm'
import { RETIRED } from './testData'
import { renderComplaints } from './testRender'

it('starts with nothing chosen while the municipality has no active type or zone', () => {
  renderComplaints(<ComplaintForm types={[RETIRED]} zones={[]} onDone={() => undefined} />)
  expect(screen.getByLabelText(t('complaints.form.type'))).toBeEmptyDOMElement()
  expect(screen.getByLabelText(t('complaints.form.zone'))).toBeEmptyDOMElement()
})
