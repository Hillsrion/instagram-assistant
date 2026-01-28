import { useState } from 'react'
import { Card } from './ui/card'
import { Button } from './ui/button'
import { Input } from './ui/input'
import { 
  ChevronDown, 
  ChevronRight, 
  Filter, 
  X, 
  Calendar,
  Users
} from 'lucide-react'

interface FiltersPanelProps {
  onParticipantChange?: (participant: string) => void
  onDateRangeChange?: (start: string, end: string) => void
  participants?: string[]
}

export function FiltersPanel({ onParticipantChange, onDateRangeChange, participants = [] }: FiltersPanelProps) {
  const [selectedParticipant, setSelectedParticipant] = useState<string>('')
  const [startDate, setStartDate] = useState<string>('')
  const [endDate, setEndDate] = useState<string>('')
  const [isOpen, setIsOpen] = useState(false)

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

  const activeFiltersCount = [
    selectedParticipant,
    startDate,
    endDate
  ].filter(Boolean).length

  return (
    <div className="w-full">
      <div 
        className="flex items-center justify-between cursor-pointer hover:bg-muted/50 p-2 rounded-lg transition-colors"
        onClick={() => setIsOpen(!isOpen)}
      >
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-muted-foreground" />
          <h3 className="text-sm font-medium">Filters</h3>
          {activeFiltersCount > 0 && (
            <span className="bg-primary text-primary-foreground text-[10px] font-bold px-1.5 py-0.5 rounded-full">
              {activeFiltersCount}
            </span>
          )}
        </div>
        {isOpen ? <ChevronDown className="h-4 w-4 text-muted-foreground" /> : <ChevronRight className="h-4 w-4 text-muted-foreground" />}
      </div>

      {isOpen && (
        <Card className="mt-2 p-4 border shadow-sm bg-card transition-all duration-200 animate-in fade-in slide-in-from-top-2">
          <div className="space-y-4">
            {/* Participant Filter */}
            <div className="space-y-2">
              <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                <Users className="h-3 w-3" />
                Participant
              </label>
              <select
                value={selectedParticipant}
                onChange={(e) => handleParticipantChange(e.target.value)}
                className="w-full h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              >
                <option value="" className="bg-background text-foreground">All Participants</option>
                {participants.map((p) => (
                  <option key={p} value={p} className="bg-background text-foreground">
                    {p.charAt(0).toUpperCase() + p.slice(1)}
                  </option>
                ))}
              </select>
            </div>

            {/* Date Range */}
            <div className="space-y-2">
              <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                <Calendar className="h-3 w-3" />
                Date Range
              </label>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <span className="text-[10px] text-muted-foreground">From</span>
                  <Input
                    type="date"
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                    className="h-8 text-xs"
                  />
                </div>
                <div className="space-y-1">
                  <span className="text-[10px] text-muted-foreground">To</span>
                  <Input
                    type="date"
                    value={endDate}
                    onChange={(e) => setEndDate(e.target.value)}
                    className="h-8 text-xs"
                  />
                </div>
              </div>
            </div>

            {/* Buttons */}
            <div className="flex gap-2 pt-2">
              <Button
                size="sm"
                onClick={handleDateRangeChange}
                className="flex-1"
              >
                Apply
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={resetFilters}
                className="flex-1"
              >
                Reset
              </Button>
            </div>

            {/* Active Filters Summary */}
            {(selectedParticipant || startDate || endDate) && (
              <div className="pt-2 border-t mt-2">
                <div className="flex flex-wrap gap-1.5">
                  {selectedParticipant && (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-secondary text-secondary-foreground text-[10px] font-medium border border-border">
                      {selectedParticipant}
                      <X className="h-2.5 w-2.5 cursor-pointer hover:text-destructive" onClick={() => handleParticipantChange('')} />
                    </span>
                  )}
                  {startDate && (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-secondary text-secondary-foreground text-[10px] font-medium border border-border">
                      From: {new Date(startDate).toLocaleDateString()}
                    </span>
                  )}
                  {endDate && (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-secondary text-secondary-foreground text-[10px] font-medium border border-border">
                      To: {new Date(endDate).toLocaleDateString()}
                    </span>
                  )}
                </div>
              </div>
            )}
          </div>
        </Card>
      )}
    </div>
  )
}
