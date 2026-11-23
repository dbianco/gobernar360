import { Button, Group, Modal, Stack, Text } from '@mantine/core'
import { type ReactNode, useCallback, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { type Confirm, ConfirmContext, type ConfirmOptions } from './confirmContext'

/** Provides `useConfirm()`: one confirmation modal for the whole site. */
export function ConfirmProvider({ children }: { children: ReactNode }) {
  const { t } = useTranslation()
  const [options, setOptions] = useState<ConfirmOptions | null>(null)
  const resolver = useRef<((answer: boolean) => void) | null>(null)

  const confirm = useCallback<Confirm>(
    (next) =>
      new Promise<boolean>((resolve) => {
        // A question still open is answered "no" before asking the next one.
        resolver.current?.(false)
        resolver.current = resolve
        setOptions(next)
      }),
    [],
  )

  function answer(value: boolean) {
    resolver.current?.(value)
    resolver.current = null
    setOptions(null)
  }

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      <Modal
        opened={options !== null}
        onClose={() => answer(false)}
        title={options?.title ?? t('app.confirmTitle')}
        centered
        // Above any modal the question is asked from.
        zIndex={400}
      >
        {options && (
          <Stack>
            {typeof options.message === 'string' ? <Text>{options.message}</Text> : options.message}
            <Group justify="flex-end">
              <Button variant="default" onClick={() => answer(false)} data-autofocus>
                {t('app.cancel')}
              </Button>
              <Button color={options.danger ? 'red' : undefined} onClick={() => answer(true)}>
                {options.confirmLabel ?? t('app.confirm')}
              </Button>
            </Group>
          </Stack>
        )}
      </Modal>
    </ConfirmContext.Provider>
  )
}
