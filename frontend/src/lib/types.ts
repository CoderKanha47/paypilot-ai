/** Shared API response types (mirror of the FastAPI Pydantic schemas). */

export type TxStatus =
  | 'pending'
  | 'completed'
  | 'declined'
  | 'failed'
  | 'cancelled'
  | 'expired'
  | 'refunded'

export interface Transaction {
  id: string
  paypal_order_id: string
  paypal_capture_id: string | null
  status: TxStatus
  paypal_status: string | null
  amount: string
  amount_minor: number
  amount_captured: string | null
  currency: string
  description: string
  customer_reference: string | null
  failure_reason: string | null
  approval_url: string | null
  mode: string
  is_demo_record: boolean
  created_at: string
  updated_at: string
  completed_at: string | null
}

export interface TransactionEvent {
  id: string
  transaction_id: string
  event_type: string
  status: TxStatus
  created_at: string
}

export interface TransactionDetail extends Transaction {
  events: TransactionEvent[]
}

export interface TransactionListResponse {
  items: Transaction[]
  total: number
  limit: number
  offset: number
  counts_by_status: Record<string, number>
}

export interface CurrencyTotal {
  currency: string
  amount: string
  count: number
}

export interface DashboardMetrics {
  primary_currency: string
  total_captured: string
  total_captured_minor: number
  total_pending: string
  total_pending_minor: number
  captured_count: number
  pending_count: number
  failed_count: number
  cancelled_count: number
  refunded_count: number
  total_transactions: number
  average_payment: string
  success_rate: number
  period_days: number
  other_currencies: CurrencyTotal[]
  demo_data_included: boolean
}

export interface MonthlyPoint {
  month: string
  label: string
  amount: string
  count: number
}

export interface StatusCount {
  status: string
  count: number
  amount: string
  currency: string
}

export interface DashboardResponse {
  metrics: DashboardMetrics
  monthly: MonthlyPoint[]
  status_distribution: StatusCount[]
  recent: Transaction[]
  generated_at: string
}

export interface AppConfig {
  app_name: string
  version: string
  environment: string
  demo_data_seeded: boolean
  demo_mode: boolean
  seed_allowed: boolean
  supported_currencies: string[]
  paypal: {
    configured: boolean
    mode: 'sandbox' | 'live' | 'disabled'
    sandbox: boolean
    client_id: string
    currency: string
    sdk_url: string
    brand_name: string
  }
  ai: {
    provider: string
    configured: boolean
    model: string
    demo_fallback: boolean
  }
  notice: string | null
}

export interface HealthResponse {
  status: 'ok' | 'degraded'
  app: string
  version: string
  environment: string
  database: string
  paypal_configured: boolean
  paypal_mode: 'sandbox' | 'live' | 'disabled'
  ai_provider: string
  ai_configured: boolean
  time: string
}

export interface CreateOrderResponse {
  transaction_id: string
  order_id: string
  status: TxStatus
  paypal_status: string | null
  amount: string
  currency: string
  description: string
  approval_url: string | null
  approve_link: string | null
  mode: 'sandbox' | 'demo'
  is_demo: boolean
  paypal_client_id: string
  sdk_currency: string
  created_at: string
  notice: string | null
}

export interface CaptureOrderResponse {
  transaction: Transaction
  already_captured: boolean
  mode: 'sandbox' | 'demo'
  notice: string | null
}

export interface ChatResponse {
  answer: string
  facts: string[]
  recommendations: string[]
  references: string[]
  confidence: string
  provider: string
  mode: 'live' | 'demo'
  latency_ms: number
  data_snapshot: Record<string, unknown>
  disclaimer: string | null
  notice: string | null
  suggestions: string[]
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface AssistantSuggestionsResponse {
  suggestions: string[]
}

export interface ReportSummaryResponse {
  generated_at: string
  currency: string
  total_captured: string
  total_pending: string
  transaction_count: number
  status_breakdown: StatusCount[]
  monthly: MonthlyPoint[]
  notes: string[]
}

export interface ApiErrorBody {
  code: string
  message: string
  errors?: string[]
  paypal_error?: Record<string, unknown>
  retry_after?: number
  provider?: string
}
