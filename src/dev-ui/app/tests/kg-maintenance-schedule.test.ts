import { describe, expect, it } from 'vitest'
import { cronToDailyTime, dailyTimeToCron } from '../utils/kgMaintenanceSchedule'

describe('kgMaintenanceSchedule', () => {
  it('converts daily time to cron and back', () => {
    expect(dailyTimeToCron('21:30')).toBe('30 21 * * *')
    expect(cronToDailyTime('30 21 * * *')).toBe('21:30')
  })

  it('rejects invalid daily time', () => {
    expect(dailyTimeToCron('25:00')).toBeNull()
    expect(dailyTimeToCron('bad')).toBeNull()
  })
})
