import { useCallback, useId, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

export function useConfirmPopover(onConfirm: () => void, disabled: boolean) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const openRef = useRef(false)
  const descriptionId = useId()

  const onOpenChange = useCallback((nextOpen: boolean): void => {
    openRef.current = nextOpen
    setOpen(nextOpen)
  }, [])

  const cancel = useCallback((): void => onOpenChange(false), [onOpenChange])
  const confirm = useCallback((): void => {
    if (disabled || !openRef.current) return
    onOpenChange(false)
    onConfirm()
  }, [disabled, onConfirm, onOpenChange])

  return {
    open,
    onOpenChange,
    cancel,
    confirm,
    descriptionId,
    cancelLabel: t('common.cancel'),
  }
}
