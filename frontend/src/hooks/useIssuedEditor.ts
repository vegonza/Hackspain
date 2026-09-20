import { useCallback, useRef, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { isUnreservedInvoiceError, fetchBillingSettings, submitVerifactuTest, downloadIssuedInvoice, fetchBillingClients, fetchBillingCompany, fetchIssuedInvoice, issueInvoice, markInvoicePaid,
  type BillingClient, type BillingCompany, type IssuedDraft, type IssuedInvoice, type IssuedLine } from '@/api/issued'
import { navigate } from '@/hooks/useAppRoute'
import { issuedTotals } from '@/hooks/issuedAmounts'
import { formatAmount, formatDateShort } from '@/lib/format'
import { supplierLogo } from '@/lib/supplierLogos'
import templateQr from '@/assets/invoice-template-qr.svg'

const emptyLine = (): IssuedLine => ({ description: '', quantity: '1', unit_price: '0', tax_rate: '21' })
const dateInput = (date: Date): string => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
const emptyDraft = (): IssuedDraft => {
  const today = new Date()
  const dueDate = new Date(today.getFullYear(), today.getMonth() + 2, 0)
  dueDate.setDate(Math.min(today.getDate(), dueDate.getDate()))
  return { client_id: '', issue_date: dateInput(today), due_date: dateInput(dueDate), notes: '', items: [emptyLine()] }
}

export function useIssuedEditor(id: string, onUpdated: (invoice: IssuedInvoice) => void) {
  const { t } = useTranslation()
  const [draft, setDraft] = useState<IssuedDraft>(emptyDraft)
  const [invoice, setInvoice] = useState<IssuedInvoice | null>(null)
  const [testEnabled, setTestEnabled] = useState(false)
  const [clients, setClients] = useState<BillingClient[]>([])
  const [company, setCompany] = useState<BillingCompany | null>(null)
  const [loading, setLoading] = useState(true)
  const [failed, setFailed] = useState(false)
  const [reload, setReload] = useState(0)
  const [busy, setBusy] = useState(false)
  const inFlight = useRef(false)
  const draftId = useRef(crypto.randomUUID())
  const [dialog, setDialog] = useState<'issue' | 'leave' | 'verifactu' | null>(null)
  const [submitted, setSubmitted] = useState(false)
  const [dirty, setDirty] = useState(false)
  const mount = useCallback((node: HTMLElement | null) => {
    if (node === null) return
    const controller = new AbortController()
    setLoading(true)
    setFailed(false)
    void Promise.all([fetchBillingClients(controller.signal), fetchBillingCompany(controller.signal),
      id === 'new' ? Promise.resolve(null) : fetchIssuedInvoice(id, controller.signal), fetchBillingSettings(controller.signal)]).then(([nextClients, nextCompany, nextInvoice, settings]) => {
      if (controller.signal.aborted) return
      setTestEnabled(settings.verifactu_test_enabled); setClients(nextClients); setCompany(nextCompany); setInvoice(nextInvoice)
      if (nextInvoice !== null) {
        setDraft({ client_id: nextInvoice.client_id, issue_date: nextInvoice.issue_date, due_date: nextInvoice.due_date, notes: nextInvoice.notes, items: nextInvoice.items })
        onUpdated(nextInvoice)
      }
    }).catch(() => { if (!controller.signal.aborted) setFailed(true) })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [id, onUpdated])
  const locked = invoice !== null || submitted
  const selectedClient = clients.find(client => client.id === draft.client_id)
  const client = locked && invoice !== null ? invoice.client : selectedClient === undefined ? null : selectedClient
  const issuer = locked && invoice !== null ? invoice.company : company
  const amounts = issuedTotals(draft.items)
  const validDraft = selectedClient !== undefined && draft.issue_date !== '' && draft.due_date >= draft.issue_date && draft.items.length > 0
    && draft.items.every(item => item.description.trim() !== '' && Number(item.quantity) > 0 && Number(item.quantity) <= 100000 && item.unit_price !== '' && Number(item.unit_price) >= 0 && Number(item.unit_price) <= 1000000 && item.tax_rate !== '' && Number(item.tax_rate) >= 0 && Number(item.tax_rate) <= 100)

  function change<K extends keyof IssuedDraft>(field: K, value: IssuedDraft[K]): void {
    setDraft(current => ({ ...current, [field]: value })); setDirty(true)
  }
  function lineChange(index: number, field: keyof IssuedLine, value: string): void {
    if (field !== 'description') value = value.replace(',', '.')
    if (field !== 'description' && !(field === 'tax_rate' ? /^\d*(\.\d{0,2})?$/ : /^\d*(\.\d{0,4})?$/).test(value)) return
    change('items', draft.items.map((line, i) => i === index ? { ...line, [field]: value } : line))
  }
  async function run(action: () => Promise<void>): Promise<void> {
    if (inFlight.current) return
    inFlight.current = true; setBusy(true)
    try { await action() } catch {
      // Request failures are displayed by the API client.
    } finally { inFlight.current = false; setBusy(false) }
  }
  function requestIssue(): void {
    if (!locked && validDraft && company !== null && !busy && !loading && !failed) setDialog('issue')
  }
  function issue(): void {
    setDialog(null)
    if (busy || loading || failed) return
    setSubmitted(true)
    void run(async () => {
      try {
        const result = await issueInvoice(invoice === null ? draftId.current : invoice.id, draft)
        setInvoice(result); setDirty(false); onUpdated(result)
        toast.success(t('issued.issuedSuccess'))
        navigate(`/invoices/issued/${result.id}`, true)
      } catch (error) {
        if (invoice === null && isUnreservedInvoiceError(error)) {
          setSubmitted(false)
          const [nextClients, nextCompany] = await Promise.all([
            fetchBillingClients(new AbortController().signal), fetchBillingCompany(new AbortController().signal),
          ])
          setClients(nextClients); setCompany(nextCompany)
          if (!nextClients.some(client => client.id === draft.client_id)) setDraft(current => ({ ...current, client_id: '' }))
        }
        throw error
      }
    })
  }
  function download(): void {
    if (invoice === null) return
    void run(async () => {
      const blob = await downloadIssuedInvoice(invoice.id)
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url; anchor.download = `${invoice.invoice_number}.pdf`; anchor.click()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    })
  }
  const testReceipt = testEnabled && invoice !== null ? invoice.verifactu_test : null
  return {
    mount, reload, loading, valuesLoading: loading && id !== 'new', isNew: id === 'new', failed, busy, locked, dirty, draft, invoice, company: issuer, client, dialog,
    companyLogo: supplierLogo(issuer === null ? null : issuer.name),
    labels: Object.fromEntries((['back', 'client', 'company', 'iban', 'paymentMethod', 'issueDate', 'dueDate', 'description', 'quantity', 'unitPrice', 'taxRate', 'amount', 'addLine', 'removeLine', 'notes', 'base', 'tax', 'total', 'issue', 'download', 'paid', 'cancel', 'close', 'preview', 'emptyClient', 'emptyCompany', 'issueConfirm', 'issueDescription', 'leaveTitle', 'leaveDescription', 'leave', 'retry', 'failed', 'invoiceLabel', 'concepts', 'paymentInfo', 'thanks', 'verifactu', 'verifactuTitle', 'verifactuDescription', 'verifactuSent', 'verifactuQr', 'verifactuLabel', 'templateQr', 'qrPending'] as const).map(key => [key, t(`issued.${key}`)])),
    title: invoice === null ? t('issued.new') : invoice.invoice_number,
    status: invoice === null ? submitted ? t('issued.status.issuing') : null : t(`issued.status.${invoice.status}`),
    canIssue: validDraft && !locked && company !== null && !busy && !loading && !failed,
    clientOptions: clients.map(client => ({ value: client.id, label: client.name })),
    totals: { base: formatAmount(amounts.base, 'EUR'), tax: formatAmount(amounts.tax, 'EUR'), total: formatAmount(amounts.total, 'EUR') },
    previewIssueDate: draft.issue_date === '' ? '' : formatDateShort(draft.issue_date, 'es-ES'),
    previewDueDate: draft.due_date === '' ? '' : formatDateShort(draft.due_date, 'es-ES'),
    previewLines: draft.items.map((line, index) => ({ ...line, price: new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR', minimumFractionDigits: 2, maximumFractionDigits: 4 }).format(Number(line.unit_price)), amount: formatAmount(amounts.lines[index].base, 'EUR') })),
    onChange: change, onLineChange: lineChange,
    onAddLine: () => change('items', [...draft.items, emptyLine()]), onRemoveLine: (index: number) => change('items', draft.items.filter((_, i) => i !== index)),
    onSubmit: (event: FormEvent<HTMLFormElement>) => { event.preventDefault(); requestIssue() },
    canSubmitVerifactu: testEnabled && invoice !== null && invoice.status !== 'issuing'
      && (testReceipt === null || testReceipt.csv === null || testReceipt.pdf_path === null),
    testRegistration: testReceipt === null || testReceipt.csv === null || testReceipt.parties === null ? null : {
      title: t('issued.testRegistration'),
      issuer: t('issued.testIssuer', testReceipt.parties.issuer),
      client: t('issued.testClient', testReceipt.parties.client),
    },
    showQr: loading || testEnabled,
    previewQr: !locked && id === 'new' ? templateQr : testReceipt === null || testReceipt.csv === null ? null : testReceipt.qr_code,
    previewQrAlt: t(!locked && id === 'new' ? 'issued.templateQr' : 'issued.verifactuQr'),
    onRequestVerifactu: () => setDialog('verifactu'),
    onSubmitVerifactu: () => {
      if (invoice === null) return
      setDialog(null)
      void run(async () => {
        const result = await submitVerifactuTest(invoice.id)
        setInvoice(result); onUpdated(result); toast.success(t('issued.verifactuSent'))
      })
    },
    onRequestIssue: requestIssue, onIssue: issue, onDownload: () => download(),
    onMarkPaid: () => { if (invoice !== null) void run(async () => { const result = await markInvoicePaid(invoice.id); setInvoice(result); onUpdated(result) }) },
    onCloseDialog: () => { if (!busy) setDialog(null) }, onBack: () => { if (dirty) setDialog('leave'); else navigate('/invoices') },
    onLeave: () => navigate('/invoices'), onRetry: () => setReload(value => value + 1),
  }
}
