import { Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Overview } from './pages/Overview'
import { Transactions } from './pages/Transactions'
import { TransactionDetail } from './pages/TransactionDetail'
import { NewPayment } from './pages/NewPayment'
import { Assistant } from './pages/Assistant'
import { Reports } from './pages/Reports'
import { Settings } from './pages/Settings'
import { PaymentResult } from './pages/PaymentResult'
import { NotFound } from './pages/NotFound'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Overview />} />
        <Route path="transactions" element={<Transactions />} />
        <Route path="transactions/:id" element={<TransactionDetail />} />
        <Route path="new-payment" element={<NewPayment />} />
        <Route path="assistant" element={<Assistant />} />
        <Route path="reports" element={<Reports />} />
        <Route path="settings" element={<Settings />} />
        <Route path="payment/result" element={<PaymentResult />} />
        <Route path="home" element={<Navigate to="/" replace />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  )
}
