/** Helpers for KG maintenance schedule UI (daily time ↔ cron). */

export const MAINTENANCE_TIMEZONE_OPTIONS = [
  { value: 'UTC', label: 'UTC' },
  { value: 'America/New_York', label: 'US Eastern' },
  { value: 'America/Chicago', label: 'US Central' },
  { value: 'America/Denver', label: 'US Mountain' },
  { value: 'America/Los_Angeles', label: 'US Pacific' },
] as const

const DAILY_CRON_RE = /^(\d{1,2})\s+(\d{1,2})\s+\*\s+\*\s+\*$/

export function dailyTimeToCron(time: string): string | null {
  const match = /^(\d{1,2}):(\d{2})$/.exec(time.trim())
  if (!match) return null
  const hour = Number(match[1])
  const minute = Number(match[2])
  if (hour < 0 || hour > 23 || minute < 0 || minute > 59) return null
  return `${minute} ${hour} * * *`
}

export function cronToDailyTime(cronExpression: string): string | null {
  const match = DAILY_CRON_RE.exec(cronExpression.trim())
  if (!match) return null
  const minute = Number(match[1])
  const hour = Number(match[2])
  if (hour < 0 || hour > 23 || minute < 0 || minute > 59) return null
  return `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`
}

export function formatMaintenanceRunOutcome(outcome: string): string {
  switch (outcome) {
    case 'started':
      return 'Started'
    case 'no-changes':
      return 'No changes'
    case 'preflight-failed':
      return 'Preflight failed'
    case 'launch-failed':
      return 'Launch failed'
    default:
      return outcome
  }
}

export function maintenanceRunOutcomeVariant(
  outcome: string,
): 'default' | 'secondary' | 'destructive' | 'outline' | 'success' {
  switch (outcome) {
    case 'started':
      return 'success'
    case 'no-changes':
      return 'secondary'
    case 'preflight-failed':
    case 'launch-failed':
      return 'destructive'
    default:
      return 'outline'
  }
}
