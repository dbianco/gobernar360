import { Alert, Button, Group, NativeSelect, Stack, Textarea, TextInput } from '@mantine/core'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { send, useAction } from './api'
import type { Benefit, Named } from './types'

/** Create a benefit the municipality hands out, or edit an existing one. */
export function BenefitForm(props: { categories: Named[]; benefit?: Benefit; onDone: () => void }) {
  const { t } = useTranslation()
  const action = useAction()
  const editing = props.benefit
  const [name, setName] = useState(editing?.name ?? '')
  const [description, setDescription] = useState(editing?.description ?? '')
  const [categoryId, setCategoryId] = useState(editing?.category.id ?? props.categories[0]?.id ?? '')
  const label = (key: string) => t(`social.parameters.${key}`)

  async function submit(event: FormEvent) {
    event.preventDefault()
    const body = { category_id: categoryId, name, description }
    const saved = await action.run(() =>
      editing ? send('PATCH', `/benefits/${editing.id}`, body) : send('POST', '/benefits', body),
    )
    if (saved) props.onDone()
  }

  return (
    <form onSubmit={submit}>
      <Stack>
        {action.error && <Alert color="red">{action.error}</Alert>}
        <TextInput
          label={label('name')}
          required
          withAsterisk={false}
          maxLength={200}
          value={name}
          onChange={(event) => setName(event.currentTarget.value)}
        />
        <Textarea
          label={label('description')}
          rows={3}
          value={description}
          onChange={(event) => setDescription(event.currentTarget.value)}
        />
        <NativeSelect
          label={label('category')}
          value={categoryId}
          onChange={(event) => setCategoryId(event.currentTarget.value)}
          data={props.categories.map((item) => ({ value: item.id, label: item.name }))}
        />
        <Group justify="flex-end">
          <Button variant="default" onClick={props.onDone}>
            {t('app.cancel')}
          </Button>
          <Button type="submit" loading={action.pending}>
            {t('app.save')}
          </Button>
        </Group>
      </Stack>
    </form>
  )
}
