import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { App } from './App'
import i18n, { i18nInitialized } from './i18n'
import './index.css'
import { navigate } from '@/hooks/useAppRoute'

async function start(): Promise<void> {
  await i18nInitialized
  document.title = i18n.t('app.name')
  if (window.location.pathname === '/') navigate('/docs', true)

  const root = createRoot(document.getElementById('root')!)
  root.render(
    <StrictMode>
      <App />
    </StrictMode>,
  )
}

void start()
