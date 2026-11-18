import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

import esAR from './locales/es-AR.json'

// All user-facing text lives in the locale file; components only use keys.
void i18n.use(initReactI18next).init({
  resources: { 'es-AR': { translation: esAR } },
  lng: 'es-AR',
  fallbackLng: 'es-AR',
  interpolation: { escapeValue: false },
  returnNull: false,
})

export default i18n
