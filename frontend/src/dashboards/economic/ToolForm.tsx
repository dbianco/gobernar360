import { Alert, Button, Group, NativeSelect, Stack, Textarea, TextInput } from '@mantine/core'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { send, useAction } from './api'
import { AUDIENCES, type Named, type Tool, type ToolSubcategory } from './types'

/** Create a support tool, or edit an existing one. */
export function ToolForm(props: {
  categories: Named[]
  subcategories: ToolSubcategory[]
  tool?: Tool
  onDone: () => void
}) {
  const { t } = useTranslation()
  const action = useAction()
  const editing = props.tool
  const [name, setName] = useState(editing?.name ?? '')
  const [description, setDescription] = useState(editing?.description ?? '')
  const [categoryId, setCategoryId] = useState(editing?.category.id ?? props.categories[0]?.id ?? '')
  const [subcategoryId, setSubcategoryId] = useState(editing?.subcategory?.id ?? '')
  const [audience, setAudience] = useState<string>(editing?.audience ?? 'both')
  const label = (key: string) => t(`economic.parameters.${key}`)
  const ownSubcategories = props.subcategories.filter((item) => item.category_id === categoryId)

  async function submit(event: FormEvent) {
    event.preventDefault()
    const body = {
      category_id: categoryId,
      subcategory_id: subcategoryId || null,
      name,
      description,
      audience,
    }
    const saved = await action.run(() =>
      editing ? send('PATCH', `/tools/${editing.id}`, body) : send('POST', '/tools', body),
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
          onChange={(event) => {
            // A subcategory belongs to one category, so changing the category clears it.
            setCategoryId(event.currentTarget.value)
            setSubcategoryId('')
          }}
          data={props.categories.map((item) => ({ value: item.id, label: item.name }))}
        />
        <NativeSelect
          label={label('subcategory')}
          value={subcategoryId}
          onChange={(event) => setSubcategoryId(event.currentTarget.value)}
          data={[
            { value: '', label: label('noSubcategory') },
            ...ownSubcategories.map((item) => ({ value: item.id, label: item.name })),
          ]}
        />
        <NativeSelect
          label={label('audience')}
          value={audience}
          onChange={(event) => setAudience(event.currentTarget.value)}
          data={AUDIENCES.map((value) => ({ value, label: t(`economic.audiences.${value}`) }))}
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
