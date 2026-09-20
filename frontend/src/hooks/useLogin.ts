import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'

import { login } from '@/api/auth'


export function useLogin(onAuthenticated: () => void) {
  const { t } = useTranslation()
  const [submitting, setSubmitting] = useState(false)

  async function onSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault()
    setSubmitting(true)
    const password = String(new FormData(event.currentTarget).get('password'))
    try {
      const status = await login(password)
      if (status === 204) onAuthenticated()
      else toast.error(t(status === 429 ? 'auth.rateLimited' : 'auth.invalid'))
    } finally {
      setSubmitting(false)
    }
  }

  return {
    onSubmit,
    submitting,
    labels: {
      title: t('auth.title'),
      description: t('auth.description'),
      password: t('auth.password'),
      submit: submitting ? t('auth.submitting') : t('auth.submit'),
    },
  }
}
