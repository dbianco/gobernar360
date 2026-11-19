import { RegistryPersonForm } from '../../platform/people/RegistryPersonForm'
import { BASE_PATH, get, send, useAction } from './api'
import type { Lookup, SocialPerson } from './types'

/** Add a person to the dashboard, or edit their registry data. */
export function PersonForm(props: { person?: SocialPerson; onDone: () => void }) {
  const action = useAction()
  const editing = props.person

  return (
    <RegistryPersonForm
      person={editing?.person}
      lookup={(dni) => get<Lookup>('/people/lookup', { dni })}
      existingPath={(id) => `${BASE_PATH}/people/${id}`}
      save={(person) =>
        editing
          ? send('PATCH', `/people/${editing.id}`, { person })
          : send('POST', '/people', { person })
      }
      action={action}
      onDone={props.onDone}
    />
  )
}
