import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { fetchExample } from '@/api/example'

type ConnectionState =
  | { status: 'idle' | 'loading' }
  | { status: 'connected'; service: string }

export function useExample() {
  const { t } = useTranslation()
  const [state, setState] = useState<ConnectionState>({ status: 'idle' })

  async function connect(): Promise<void> {
    setState({ status: 'loading' })

    try {
      const response = await fetchExample()
      setState({ status: 'connected', service: response.service })
    } catch {
      setState({ status: 'idle' })
      toast.error(t('example.error'))
    }
  }

  return {
    appName: t('app.name'),
    title: t('example.title'),
    description: t('example.description'),
    buttonLabel: t('example.connect'),
    loadingLabel: t('example.loading'),
    message: state.status === 'connected' ? t('example.connected', { service: state.service }) : '',
    isLoading: state.status === 'loading',
    onConnect: connect,
  }
}
