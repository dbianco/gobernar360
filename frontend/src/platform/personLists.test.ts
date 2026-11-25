import { expect, it } from 'vitest'

const sources = import.meta.glob('../**/*.tsx', { query: '?raw', import: 'default', eager: true })

it('lists people only where one can type to find them', () => {
  // A plain list built from people's names: use <PersonSelect> or <PeopleSelect>.
  const plain = Object.entries(sources)
    .filter(([path]) => !path.includes('.test.') && !path.endsWith('PersonSelect.tsx'))
    .filter(([, source]) => /value: (\w+)\.id, label: \1\.full_name/.test(source as string))
    .map(([path]) => path)

  expect(plain).toEqual([])
})
