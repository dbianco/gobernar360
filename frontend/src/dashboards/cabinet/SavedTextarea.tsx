import { Textarea, type TextareaProps } from '@mantine/core'
import { useState } from 'react'

/**
 * A text area that saves what was typed when it loses focus, so nothing written during a
 * meeting waits for a button. If saving fails the text stays, and leaving it tries again.
 */
export function SavedTextarea({
  saved,
  onSave,
  ...props
}: Omit<TextareaProps, 'value' | 'onChange' | 'onBlur'> & {
  saved: string
  onSave: (text: string) => void
}) {
  const [text, setText] = useState(saved)
  // What is saved may change under it (another person, another screen): follow it unless
  // there is something typed and not saved.
  const [known, setKnown] = useState(saved)
  if (known !== saved) {
    setKnown(saved)
    if (text === known) setText(saved)
  }
  return (
    <Textarea
      {...props}
      value={text}
      onChange={(event) => setText(event.currentTarget.value)}
      onBlur={() => {
        if (text.trim() !== saved) onSave(text)
      }}
    />
  )
}
