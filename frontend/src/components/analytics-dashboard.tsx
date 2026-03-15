import { useEffect, useState } from 'react'
import { Card } from './ui/card'
import { FiltersPanel } from './filters-panel'
import {
  getAnalyticsOverview,
  getParticipantStats,
  getMonthlyTimeline,
  getMessageCount
} from '../lib/api'

interface AnalyticsData {
  total_messages: number
  total_conversations: number
  total_chunks: number
  total_participants: number
  date_start: string
  date_end: string
}

interface ParticipantStat {
  message_count: number
  conversations: number
  chunks: number
  date_start: string
  date_end: string
}

interface TimelineData {
  year: number
  month: number
  month_name: string
  message_count: number
}

export function AnalyticsDashboard() {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  
  // Data state
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null)
  const [participantStats, setParticipantStats] = useState<Record<string, ParticipantStat>>({})
  const [monthlyData, setMonthlyData] = useState<TimelineData[]>([])
  
  // Filter state
  const [selectedParticipant, setSelectedParticipant] = useState<string>('')
  const [startDate, setStartDate] = useState<string>('')
  const [endDate, setEndDate] = useState<string>('')
  const [filteredMessageCount, setFilteredMessageCount] = useState<number | null>(null)

  // Initial Data Load
  useEffect(() => {
    async function fetchInitialData() {
      try {
        setLoading(true)
        const [overview, stats] = await Promise.all([
          getAnalyticsOverview(),
          getParticipantStats()
        ])

        setAnalytics(overview)
        setParticipantStats(stats.participants)
        setFilteredMessageCount(overview.total_messages)
        setError(null)
      } catch (err) {
        console.error('Error fetching initial analytics:', err)
        setError('Failed to load analytics data')
      } finally {
        setLoading(false)
      }
    }

    fetchInitialData()
  }, [])

  // Dynamic Data Load (Filters)
  useEffect(() => {
    async function fetchFilteredData() {
      try {
        // 1. Get filtered message count
        const countData = await getMessageCount(
          selectedParticipant,
          startDate,
          endDate
        )
        setFilteredMessageCount(countData.count)

        // 2. Get timeline (dependent on participant only for now)
        const timelineData = await getMonthlyTimeline(selectedParticipant)
        setMonthlyData(timelineData.timeline)

      } catch (err) {
        console.error('Error fetching filtered data:', err)
        // Don't set global error here to avoid blocking the UI, just log
      }
    }

    fetchFilteredData()
  }, [selectedParticipant, startDate, endDate])

  if (loading && !analytics) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-gray-500">Chargement des analyses...</div>
      </div>
    )
  }

  if (error || !analytics) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-red-500">{error || 'Erreur lors du chargement des données'}</div>
      </div>
    )
  }

  // Sort participants by message count
  const sortedParticipants = Object.entries(participantStats)
    .sort(([, a], [, b]) => b.message_count - a.message_count)
    .slice(0, 10)

  // Format date for display
  const formatDate = (dateStr: string) => {
    if (!dateStr) return 'N/A'
    return new Date(dateStr).toLocaleDateString('fr-FR')
  }

  const handleParticipantChange = (participant: string) => {
    setSelectedParticipant(participant)
  }

  const handleDateRangeChange = (start: string, end: string) => {
    setStartDate(start)
    setEndDate(end)
  }

  return (
    <div className="h-full overflow-y-auto bg-linear-to-br from-slate-50 to-slate-100 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-4xl font-bold text-gray-900 mb-2">Analytics</h1>
            <p className="text-gray-600">
              {formatDate(analytics.date_start)} — {formatDate(analytics.date_end)}
            </p>
          </div>
          <div className="w-full md:w-auto">
             {/* We can place actions here if needed */}
          </div>
        </div>

        {/* Filters */}
        <div className="mb-8">
          <FiltersPanel 
            participants={Object.keys(participantStats).sort()}
            onParticipantChange={handleParticipantChange}
            onDateRangeChange={handleDateRangeChange}
          />
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <Card className="p-6 bg-white shadow-md hover:shadow-lg transition border-l-4 border-l-blue-500">
            <div className="text-sm font-medium text-gray-600">
              {selectedParticipant || startDate || endDate ? 'Filtered Messages' : 'Total Messages'}
            </div>
            <div className="text-3xl font-bold text-gray-900 mt-2">
              {filteredMessageCount?.toLocaleString() ?? '-'}
            </div>
            {(selectedParticipant || startDate || endDate) && (
              <div className="text-xs text-gray-500 mt-1">
                of {analytics.total_messages.toLocaleString()} total
              </div>
            )}
          </Card>

          <Card className="p-6 bg-white shadow-md hover:shadow-lg transition">
            <div className="text-sm font-medium text-gray-600">Participants</div>
            <div className="text-3xl font-bold text-gray-900 mt-2">
              {analytics.total_participants}
            </div>
          </Card>

          <Card className="p-6 bg-white shadow-md hover:shadow-lg transition">
            <div className="text-sm font-medium text-gray-600">Conversations</div>
            <div className="text-3xl font-bold text-gray-900 mt-2">
              {analytics.total_conversations}
            </div>
          </Card>

          <Card className="p-6 bg-white shadow-md hover:shadow-lg transition">
            <div className="text-sm font-medium text-gray-600">Chunks Indexed</div>
            <div className="text-3xl font-bold text-gray-900 mt-2">
              {analytics.total_chunks}
            </div>
          </Card>
        </div>

        {/* Two column layout */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Top Participants */}
          <Card className="p-6 bg-white shadow-md">
            <h2 className="text-xl font-bold text-gray-900 mb-4">Top Participants</h2>
            <div className="space-y-4">
              {sortedParticipants.length > 0 ? (
                sortedParticipants.map(([name, stats], idx) => (
                  <div
                    key={name}
                    className="flex items-center justify-between pb-3 border-b border-gray-100 last:border-b-0"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-blue-500 text-white flex items-center justify-center text-sm font-bold">
                        {idx + 1}
                      </div>
                      <div>
                        <div className="font-medium text-gray-900">{name}</div>
                        <div className="text-sm text-gray-500">
                          {stats.conversations} conversation{stats.conversations !== 1 ? 's' : ''}
                        </div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="font-bold text-gray-900">{stats.message_count}</div>
                      <div className="text-xs text-gray-500">messages</div>
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-gray-500 text-center py-4">No data available</div>
              )}
            </div>
          </Card>

          {/* Monthly Activity */}
          <Card className="p-6 bg-white shadow-md">
            <h2 className="text-xl font-bold text-gray-900 mb-4">Monthly Activity</h2>
            <div className="space-y-3 max-h-96 overflow-y-auto">
              {monthlyData.length > 0 ? (
                monthlyData
                  .slice(-12) // Show last 12 months
                  .map((data) => {
                    const maxMessages = Math.max(...monthlyData.map(d => d.message_count), 1)
                    const percentage = (data.message_count / maxMessages) * 100

                    return (
                      <div key={`${data.year}-${data.month}`}>
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-sm text-gray-700">
                            {data.month_name} {data.year}
                          </span>
                          <span className="text-sm font-medium text-gray-900">
                            {data.message_count}
                          </span>
                        </div>
                        <div className="w-full bg-gray-200 rounded-full h-2">
                          <div
                            className="bg-blue-500 h-2 rounded-full transition-all"
                            style={{ width: `${percentage}%` }}
                          />
                        </div>
                      </div>
                    )
                  })
              ) : (
                <div className="text-gray-500 text-center py-4">No monthly data available</div>
              )}
            </div>
          </Card>
        </div>

        {/* Summary Stats */}
        <Card className="mt-8 p-6 bg-white shadow-md">
          <h2 className="text-xl font-bold text-gray-900 mb-4">Summary</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <h3 className="font-medium text-gray-700 mb-2">Activity Metrics</h3>
              <ul className="space-y-2 text-sm text-gray-600">
                <li>
                  <span className="font-medium">Average messages per conversation:</span>{' '}
                  {analytics.total_conversations > 0
                    ? Math.round(analytics.total_messages / analytics.total_conversations)
                    : 0}
                </li>
                <li>
                  <span className="font-medium">Average messages per participant:</span>{' '}
                  {analytics.total_participants > 0
                    ? Math.round(analytics.total_messages / analytics.total_participants)
                    : 0}
                </li>
                <li>
                  <span className="font-medium">Messages per chunk:</span>{' '}
                  {analytics.total_chunks > 0
                    ? Math.round(analytics.total_messages / analytics.total_chunks)
                    : 0}
                </li>
              </ul>
            </div>

            <div>
              <h3 className="font-medium text-gray-700 mb-2">Coverage</h3>
              <ul className="space-y-2 text-sm text-gray-600">
                <li>
                  <span className="font-medium">Time span:</span>{' '}
                  {analytics.date_start && analytics.date_end
                    ? `${Math.round(
                        (new Date(analytics.date_end).getTime() -
                          new Date(analytics.date_start).getTime()) /
                          (1000 * 60 * 60 * 24)
                      )} days`
                    : 'N/A'}
                </li>
                <li>
                  <span className="font-medium">Data indexed:</span> {analytics.total_chunks} chunks
                </li>
                <li>
                  <span className="font-medium">Participants tracked:</span>{' '}
                  {analytics.total_participants}
                </li>
              </ul>
            </div>
          </div>
        </Card>
      </div>
    </div>
  )
}
