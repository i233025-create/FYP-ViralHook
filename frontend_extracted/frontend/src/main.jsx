import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
// Fonts are bundled (no Google Fonts request), so the app also works offline.
import '@fontsource-variable/inter'
import '@fontsource/bebas-neue'
import '@fontsource-variable/jetbrains-mono'
import './index.css'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>
)
