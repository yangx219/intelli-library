import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { AuthSessionProvider } from './AuthSession'
import './index.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AuthSessionProvider>
      <App />
    </AuthSessionProvider>
  </StrictMode>,
)
