import { useState } from 'react'
import { Card } from './ui/card'

interface FiltersPanelProps {
  onParticipantChange?: (participant: string) => void
  onDateRangeChange?: (start: string, end: string) => void
  participants?: string[]
}

export function FiltersPanel({ onParticipantChange, onDateRangeChange, participants = [] }: FiltersPanelProps) {
  const [selectedParticipant, setSelectedParticipant] = useState<string>('')
  const [startDate, setStartDate] = useState<string>('')
  const [endDate, setEndDate] = useState<string>('')
  const [isOpen, setIsOpen] = useState(true)

  const handleParticipantChange = (participant: string) => {
    setSelectedParticipant(participant)
    onParticipantChange?.(participant)
  }

  const handleDateRangeChange = () => {
    onDateRangeChange?.(startDate, endDate)
  }

  const resetFilters = () => {
    setSelectedParticipant('')
    setStartDate('')
    setEndDate('')
    onParticipantChange?.('')
    onDateRangeChange?.('', '')
  }

  return (
    <Card className="bg-white shadow-md p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900">Filters</h3>
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="text-gray-500 hover:text-gray-700 transition"
        >
          {isOpen ? '▼' : '▶'}
        </button>
      </div>

      {isOpen && (
        <div className="space-y-4">
          {/* Participant Filter */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Participant</label>
            <select
              value={selectedParticipant}
              onChange={(e) => handleParticipantChange(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white text-gray-900"
            >
              <option value="">All Participants</option>
              {participants.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </div>

          {/* Date Range */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">From</label>
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white text-gray-900"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">To</label>
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white text-gray-900"
              />
            </div>
          </div>

          {/* Buttons */}
          <div className="flex gap-2">
            <button
              onClick={handleDateRangeChange}
              className="flex-1 px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition font-medium"
            >
              Apply
            </button>
            <button
              onClick={resetFilters}
              className="flex-1 px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition font-medium"
            >
              Reset
            </button>
          </div>

          {/* Active Filters Summary */}
          {(selectedParticipant || startDate || endDate) && (
            <div className="mt-4 p-3 bg-blue-50 rounded-lg border border-blue-200">
              <p className="text-sm text-blue-900 font-medium mb-2">Active Filters:</p>
              <ul className="text-xs text-blue-800 space-y-1">
                {selectedParticipant && <li>• Participant: {selectedParticipant}</li>}
                {startDate && <li>• From: {new Date(startDate).toLocaleDateString()}</li>}
                {endDate && <li>• To: {new Date(endDate).toLocaleDateString()}</li>}
              </ul>
            </div>
          )}
        </div>
      )}
    </Card>
  )
}
