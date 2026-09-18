import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { App } from './App'
import i18n, { i18nInitialized } from './i18n'
import './index.css'
import { fetchDocuments, type Document } from '@/api/documents'
import { DocumentSkeleton } from '@/components/documents/DocumentSkeleton'
import { Toaster } from '@/components/ui/sonner'

async function start(): Promise<void> {
  await i18nInitialized
  document.title = i18n.t('app.name')

  const root = createRoot(document.getElementById('root')!)
  root.render(<><Toaster position="top-center" /><DocumentSkeleton /></>)
  let documents: Document[] = []
  try {
    documents = await fetchDocuments()
  } catch {
    // The API client shows the error; uploads remain available.
  }
  root.render(
    <StrictMode>
      <App initialDocuments={documents} />
    </StrictMode>,
  )
}

void start()
