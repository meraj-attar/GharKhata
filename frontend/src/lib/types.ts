export type TransactionType = 'income' | 'expense'
export type ExpenseCategory = 'Grocery' | 'Bills' | 'Education' | 'Medical' | 'EMI / Debt' | 'Personal'
export type Category = 'Income' | ExpenseCategory

export type Transaction = {
  id: string
  user_id: string
  type: TransactionType
  amount: string
  category: Category
  date: string
  description: string | null
  created_at: string
  updated_at: string
}
export type TransactionForm = Pick<Transaction, 'type' | 'amount' | 'category' | 'date' | 'description'>
export type CategoryTotal = { category: ExpenseCategory; amount: string }
export type Totals = {
  total_income: string
  total_expenses: string
  remaining_balance: string
  categories: CategoryTotal[]
}
export type DashboardData = Totals & {
  daily_expenses: { day: number; amount: string }[]
  recent_transactions: Transaction[]
}
export type ReportData = Totals & {
  start_date: string
  end_date: string
  transactions: Transaction[]
}
export type Session = { email: string; csrf_token: string }
export const expenseCategories: ExpenseCategory[] = [
  'Grocery', 'Bills', 'Education', 'Medical', 'EMI / Debt', 'Personal',
]
