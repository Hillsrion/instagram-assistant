import { useMemo, useState } from "react"
import { Check, Search, Users, User } from "lucide-react"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"

import { cn } from "@/lib/utils"

interface SearchPopoverProps {
  participantNames: string[]
  selectedParticipant: string
  onSelectParticipant: (name: string) => void
  isBroadSearch: boolean // NEW
  onBroadSearchChange: (isBroad: boolean) => void // NEW
  selectedGroup: string
  onSelectGroup: (group: string) => void
  children: React.ReactNode
}

// Mock groups for the UI
const MOCK_GROUPS = [
  { id: "family", name: "Famille", count: 4 },
  { id: "work", name: "Travail", count: 8 },
  { id: "friends", name: "Amis proches", count: 12 },
]

export function SearchPopover({
  participantNames,
  selectedParticipant,
  onSelectParticipant,
  isBroadSearch, // NEW
  onBroadSearchChange, // NEW
  selectedGroup,
  onSelectGroup,
  children
}: SearchPopoverProps) {
  const [search, setSearch] = useState("")
  const [open, setOpen] = useState(false)

  // Filter participants based on search
  const filteredParticipants = useMemo(() => {
    return participantNames.filter(p => 
      p.toLowerCase().includes(search.toLowerCase())
    )
  }, [participantNames, search])

  // Sort participants: selected first, then alphabetical
  const sortedParticipants = useMemo(() => {
    return [...filteredParticipants].sort((a, b) => {
      // If one is selected, it goes first
      if (a === selectedParticipant) return -1
      if (b === selectedParticipant) return 1
      // Otherwise alphabetical
      return a.localeCompare(b)
    })
  }, [filteredParticipants, selectedParticipant])

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        {children}
      </PopoverTrigger>
      <PopoverContent className="w-[600px] p-0" align="start">
        <div className="flex bg-background h-[400px]">
          {/* LEFT SIDE: GROUPS (Mocked) */}
          <div className="w-[200px] border-r bg-muted/30 p-2 flex flex-col gap-1">
            <div className="px-2 py-1.5 text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Groupes
            </div>
            {MOCK_GROUPS.map(group => (
              <button
                key={group.id}
                className={cn( // Corrected formatting
                  "flex items-center justify-between w-full px-2 py-1.5 text-sm rounded-md text-left group transition-colors",
                  selectedGroup === group.id 
                    ? "bg-primary/10 text-primary font-medium" 
                    : "hover:bg-accent text-foreground/80"
                )}
                onClick={() => {
                  onSelectGroup(selectedGroup === group.id ? "" : group.id)
                  // Optional: clear participant selection if group is selected? 
                  // For now, let's allow both or assume logic is handled parent side.
                  // Ideally, if group is selected, we might want to auto-select participants, but that's complex mock.
                }}
              >
                <div className="flex items-center gap-2">
                   <Users className="h-4 w-4 opacity-70" />
                   <span>{group.name}</span>
                </div>
                {selectedGroup === group.id && <Check className="h-3 w-3" />}
                {selectedGroup !== group.id && (
                    <Badge variant="secondary" className="h-5 px-1.5 text-[10px]">
                        {group.count}
                    </Badge>
                )}
              </button>
            ))}
            
            <div className="mt-auto p-2">
               <div className="text-[10px] text-muted-foreground text-center">
                 Groupes gérés par l'utilisateur (Bientôt)
               </div>
            </div>
          </div>

          {/* RIGHT SIDE: PARTICIPANTS */}
          <div className="flex-1 flex flex-col min-w-0">
            {/* Search Header */}
            <div className="p-3 border-b flex flex-col gap-2">
               <div className="relative">
                 <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                 <Input
                   placeholder="Rechercher des participants..."
                   className="pl-9 h-9 border-none bg-muted/50 focus-visible:ring-0 focus-visible:bg-muted"
                   value={search}
                   onChange={(e) => setSearch(e.target.value)}
                 />
               </div>

               {/* Broad Search Toggle */}
               {selectedParticipant && (
                 <div className="flex items-center gap-2 px-1">
                    <input 
                      type="checkbox" 
                      id="popover-broad-search"
                      checked={isBroadSearch}
                      onChange={(e) => onBroadSearchChange(e.target.checked)}
                      className="h-3.5 w-3.5 rounded border-gray-300 text-primary focus:ring-primary"
                    />
                    <label htmlFor="popover-broad-search" className="text-[11px] font-medium text-muted-foreground cursor-pointer select-none">
                      Inclure les mentions (recherche large)
                    </label>
                 </div>
               )}
            </div>

            {/* List */}
            <ScrollArea className="flex-1">
              <div className="p-2">
                <div className="px-2 py-1.5 text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1">
                  Participants ({filteredParticipants.length})
                </div>
                
                <div className="space-y-0.5">
                  <button
                     onClick={() => {
                       onSelectParticipant("")
                       setOpen(false)
                     }}
                     className={cn(
                       "flex items-center w-full px-2 py-2 text-sm rounded-md text-left transition-colors",
                       selectedParticipant === "" 
                         ? "bg-primary/10 text-primary font-medium" 
                         : "hover:bg-accent text-foreground/80"
                     )}
                  >
                     <div className="flex items-center gap-2 flex-1">
                        <Users className="h-4 w-4" />
                        <span>Tous les participants</span>
                     </div>
                     {selectedParticipant === "" && <Check className="h-4 w-4" />}
                  </button>

                  {sortedParticipants.map(name => (
                    <button
                      key={name}
                      onClick={() => {
                        // Toggle selection
                        onSelectParticipant(selectedParticipant === name ? "" : name)
                        setOpen(false) // Optional: keep open if multi-select
                      }}
                       className={cn(
                         "flex items-center w-full px-2 py-2 text-sm rounded-md text-left transition-colors",
                         selectedParticipant === name
                           ? "bg-primary/10 text-primary font-medium" 
                           : "hover:bg-accent text-foreground/80"
                       )}
                    >
                       <div className="flex items-center gap-2 flex-1 min-w-0">
                          <User className="h-4 w-4 opacity-70 shrink-0" />
                          <span className="truncate">{name}</span>
                       </div>
                       {selectedParticipant === name && <Check className="h-4 w-4 shrink-0" />}
                    </button>
                  ))}

                  {filteredParticipants.length === 0 && (
                    <div className="p-8 text-center text-sm text-muted-foreground">
                      Aucun participant trouvé.
                    </div>
                  )}
                </div>
              </div>
            </ScrollArea>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  )
}
