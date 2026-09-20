import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { App } from './App'
import i18n, { i18nInitialized } from './i18n'
import './index.css'
import { navigate } from '@/hooks/useAppRoute'
import { hasSession, login } from '@/api/auth'
import { LoginPage } from '@/pages/LoginPage'

async function authenticate(): Promise<boolean> {
  const url = new URL(window.location.href)
  const password = url.searchParams.get('password')
  if (password === null) return await hasSession()
  url.searchParams.delete('password')
  window.history.replaceState(null, '', `${url.pathname}${url.search}${url.hash}`)
  return await login(password) === 204
}

async function start(): Promise<void> {
  await i18nInitialized
  document.title = i18n.t('app.name')
  const root = createRoot(document.getElementById('root')!)
  const renderApp = () => {
    if (window.location.pathname === '/') navigate('/invoices', true)
    root.render(<StrictMode><App /></StrictMode>)
  }
  if (await authenticate().catch(() => false)) renderApp()
  else root.render(<StrictMode><LoginPage onAuthenticated={renderApp} /></StrictMode>)
}

void start()
