import { createFileRoute } from '@tanstack/react-router'
import { AnalyticsDashboard } from '@/components/analytics-dashboard'

export const Route = createFileRoute('/analytics')({
  component: AnalyticsPage,
})

function AnalyticsPage() {
  return <AnalyticsDashboard />
}
