import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import translation from '@/locales/es/translation.json'

export const i18nInitialized = i18n.use(initReactI18next).init({
  lng: 'es',
  supportedLngs: ['es'],
  fallbackLng: false,
  resources: { es: { translation } },
  interpolation: { escapeValue: false },
  react: { useSuspense: false },
})

export default i18n
