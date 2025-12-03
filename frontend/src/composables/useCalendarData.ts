// src/composables/useCalendarData.ts
import { ref, computed, type Ref } from 'vue';
import type { CalendarResult } from '@/types/challenges';

export interface CalendarDay {
  day: number;
  month: number;
  isCompleted: boolean;
  isMissing: boolean;
  hasCache: boolean;
  count: number;
}

export interface CalendarMonth {
  month: number;
  name: string;
  days: CalendarDay[];
  completedCount: number;
  missingCount: number;
  completionRate: number;
}

export function useCalendarData(calendarResult: Ref<CalendarResult | null>) {
  const monthNames = [
    'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
    'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre'
  ];

  const daysInMonth = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]; // Max days considering leap year

  const calendarData = computed(() => {
    if (!calendarResult.value) {
      return { months: [], totalCompletionRate365: 0, totalCompletionRate366: 0 };
    }

    const months: CalendarMonth[] = [];

    for (let month = 1; month <= 12; month++) {
      const days: CalendarDay[] = [];
      const daysInCurrentMonth = daysInMonth[month - 1];
      const monthStr = month.toString().padStart(2, '0');
      
      for (let day = 1; day <= daysInCurrentMonth; day++) {
        const dayStr = `${monthStr}-${day.toString().padStart(2, '0')}`;
        const isCompleted = calendarResult.value.completed_days.some(d => d.day === dayStr);
        const dayData = calendarResult.value.completed_days.find(d => d.day === dayStr);
        const count = dayData?.count || 0;
        
        const missingDays = calendarResult.value.missing_days_by_month[monthStr] || [];
        const isMissing = missingDays.includes(dayStr);

        days.push({
          day,
          month,
          isCompleted,
          isMissing,
          hasCache: isCompleted || isMissing,
          count
        });
      }

      const completedCount = days.filter(d => d.isCompleted).length;
      const missingCount = days.filter(d => d.isMissing).length;
      const completionRate = daysInCurrentMonth > 0 ? (completedCount / daysInCurrentMonth) * 100 : 0;

      months.push({
        month,
        name: monthNames[month - 1],
        days,
        completedCount,
        missingCount,
        completionRate
      });
    }

    return {
      months,
      totalCompletionRate365: calendarResult.value.completion_rate_365 * 100,
      totalCompletionRate366: calendarResult.value.completion_rate_366 * 100
    };
  });

  return {
    calendarData,
    monthNames
  };
}