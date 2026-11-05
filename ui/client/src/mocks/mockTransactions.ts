
// mockTransactions.ts
// Drop this into your StackBlitz practice project to rehearse
// the "Transactions list" + "Load more" + "Currency conversion" tasks
// without needing a real backend.

export type TransactionStatus = 'pending' | 'completed' | 'failed';

export interface Transaction {
  id: string;
  date: string; // ISO 8601
  merchant: string;
  amount: number; // in minor units would be safer in real fintech code (see prep guide notes)
  currency: string; // ISO 4217, e.g. 'USD'
  status: TransactionStatus;
}

const MERCHANTS = [
  'Amazon', 'Uber', 'Spotify', 'Netflix', 'Tesco',
  'Shell', 'Airbnb', 'Apple', 'Deliveroo', 'IKEA',
  'Starbucks', 'H&M', 'ASOS', 'Booking.com', 'Zara',
];

const CURRENCIES = ['USD', 'EUR', 'GBP', 'JPY'];
const STATUSES: TransactionStatus[] = ['completed', 'completed', 'completed', 'pending', 'failed'];
// weighted so most transactions are 'completed' — mirrors realistic data

function randomFrom<T>(arr: T[]): T {
  return arr[Math.floor(Math.random() * arr.length)];
}

function randomAmount(): number {
  // mix of small and large amounts, occasionally negative (refunds)
  const base = Math.round((Math.random() * 500 + 1) * 100) / 100;
  return Math.random() < 0.1 ? -base : base;
}

function randomDate(daysAgoMax: number): string {
  const daysAgo = Math.floor(Math.random() * daysAgoMax);
  const d = new Date();
  d.setDate(d.getDate() - daysAgo);
  return d.toISOString();
}

/**
 * Generates a full in-memory dataset once, sorted newest-first —
 * simulates "the database" your fake API paginates over.
 */
function generateTransactions(count: number): Transaction[] {
  const list: Transaction[] = Array.from({ length: count }, (_, i) => ({
    id: `txn_${(i + 1).toString().padStart(4, '0')}`,
    date: randomDate(90),
    merchant: randomFrom(MERCHANTS),
    amount: randomAmount(),
    currency: randomFrom(CURRENCIES),
    status: randomFrom(STATUSES),
  }));
  return list.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());
}

const ALL_TRANSACTIONS = generateTransactions(87); // odd number on purpose — forces you to handle a final partial page

// ---------------------------------------------------------------------------
// Fake API layer — simulates latency, pagination, and occasional failure
// so you can practice loading states, error states, and "Load more".
// ---------------------------------------------------------------------------

export interface TransactionsPage {
  data: Transaction[];
  nextCursor: string | null; // null means no more pages
}

const PAGE_SIZE = 10;
const SIMULATED_LATENCY_MS = 600;
const SIMULATED_FAILURE_RATE = 0.1; // ~1 in 10 calls fails — good for testing error handling

/**
 * fetchTransactions
 * Cursor-based pagination: pass the previous response's `nextCursor` to get the next page.
 * Pass `undefined` (or omit) to get the first page.
 *
 * Supports cancellation via AbortSignal — practice wiring this up with AbortController
 * to guard against race conditions (see prep guide, Resilience section).
 */
export function fetchTransactions(
  cursor?: string,
  signal?: AbortSignal
): Promise<TransactionsPage> {
  const startIndex = cursor ? parseInt(cursor, 10) : 0;
  console.log(`fetchTransactions called with cursor=${cursor}, startIndex=${startIndex}`);
  return new Promise((resolve, reject) => {
    const timeoutId = setTimeout(() => {
      if (signal?.aborted) {
        reject(new DOMException('Aborted', 'AbortError'));
        return;
      }

      if (Math.random() < SIMULATED_FAILURE_RATE) {
        reject(new Error('Network error: failed to fetch transactions. Please try again.'));
        return;
      }

      const page = ALL_TRANSACTIONS.slice(startIndex, startIndex + PAGE_SIZE);
      const nextIndex = startIndex + PAGE_SIZE;
      const nextCursor = nextIndex < ALL_TRANSACTIONS.length ? String(nextIndex) : null;

      resolve({ data: page, nextCursor });
    }, SIMULATED_LATENCY_MS);

    signal?.addEventListener('abort', () => {
      clearTimeout(timeoutId);
      reject(new DOMException('Aborted', 'AbortError'));
    });
  });
}

// ---------------------------------------------------------------------------
// Fake exchange rates — for the currency conversion task
// ---------------------------------------------------------------------------

export interface ExchangeRates {
  base: string;
  rates: Record<string, number>;
}

const RATE_TABLE: Record<string, number> = {
  USD: 1,
  EUR: 0.92,
  GBP: 0.79,
  JPY: 156.3,
};

/**
 * fetchExchangeRates
 * Always quotes rates relative to USD. Simulates latency; occasionally
 * omits a currency to practice handling a "missing rate" edge case.
 */
export function fetchExchangeRates(signal?: AbortSignal): Promise<ExchangeRates> {
  return new Promise((resolve, reject) => {
    const timeoutId = setTimeout(() => {
      if (signal?.aborted) {
        reject(new DOMException('Aborted', 'AbortError'));
        return;
      }
      resolve({ base: 'USD', rates: { ...RATE_TABLE } });
    }, 300);

    signal?.addEventListener('abort', () => {
      clearTimeout(timeoutId);
      reject(new DOMException('Aborted', 'AbortError'));
    });
  });
}

/**
 * Pure conversion function — no side effects, easy to unit test in isolation.
 * Converts `amount` in `from` currency to `to` currency using USD-based rates.
 */
export function convertAmount(
  amount: number,
  from: string,
  to: string,
  rates: Record<string, number>
): number | null {
  const fromRate = rates[from];
  const toRate = rates[to];
  if (fromRate == null || toRate == null || !Number.isFinite(amount)) {
    return null; // caller should show a contextual error, not crash
  }
  const amountInUsd = amount / fromRate;
  return Math.round(amountInUsd * toRate * 100) / 100;
}
