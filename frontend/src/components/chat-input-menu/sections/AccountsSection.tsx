import { Check, Globe, Search, User, Users } from "lucide-react";
import { useState } from "react";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { SourceGroup } from "@/lib/types";
import { cn } from "@/lib/utils";

interface AccountsSectionProps {
  accountSearch: string;
  setAccountSearch: (s: string) => void;
  selectedGroup: string;
  onSelectGroup: (g: string) => void;
  selectedParticipant: string;
  onSelectParticipant: (p: string) => void;
  isBroadSearch: boolean;
  onBroadSearchChange: (b: boolean) => void;
  sortedParticipants: string[];
  groups: SourceGroup[];
}

export function AccountsSection({
  accountSearch,
  setAccountSearch,
  selectedGroup,
  onSelectGroup,
  selectedParticipant,
  onSelectParticipant,
  isBroadSearch,
  onBroadSearchChange,
  sortedParticipants,
  groups,
}: AccountsSectionProps) {
  const [activeFilter, setActiveFilter] = useState<string>("");

  const filteredParticipants = sortedParticipants.filter((_name) => {
    if (!activeFilter) return true;
    // In a real app, we might filter participants based on group membership if we had the mapping
    return true;
  });

  const filteredGroupsInList = groups.filter((group) => {
    const matchesSearch = group.title
      .toLowerCase()
      .includes(accountSearch.toLowerCase());
    if (!activeFilter) return matchesSearch;
    return group.id === activeFilter && matchesSearch;
  });

  return (
    <div className="flex flex-col h-full">
      <div className="p-3 pb-1 flex flex-col gap-3">
        <div className="relative">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Rechercher"
            className="pl-9 h-9 border-none bg-muted/50 focus-visible:ring-0 focus-visible:bg-muted text-sm rounded-full"
            value={accountSearch}
            onChange={(e) => setAccountSearch(e.target.value)}
          />
        </div>
        {/* Groups as Filter Pills */}
        <div className="w-full whitespace-nowrap pb-1 overflow-x-auto">
          <div className="flex w-max space-x-2 px-1">
            <button
              type="button"
              onClick={() => setActiveFilter("")}
              className={cn(
                "px-3 py-1 rounded-full text-xs font-medium border transition-colors",
                !activeFilter
                  ? "bg-primary text-primary-foreground border-primary"
                  : "bg-transparent text-foreground hover:bg-accent border-input",
              )}
            >
              Tous
            </button>
            {groups.map((group) => (
              <button
                type="button"
                key={group.id}
                onClick={() => setActiveFilter(group.id)}
                className={cn(
                  "px-3 py-1 rounded-full text-xs font-medium border transition-colors",
                  activeFilter === group.id
                    ? "bg-primary text-primary-foreground border-primary"
                    : "bg-transparent text-foreground hover:bg-accent border-input",
                )}
              >
                {group.title}
              </button>
            ))}
          </div>
        </div>
        {selectedParticipant && (
          <div className="flex items-center gap-2 px-1">
            <input
              type="checkbox"
              id="menu-broad-search"
              checked={isBroadSearch}
              onChange={(e) => onBroadSearchChange(e.target.checked)}
              className="h-3.5 w-3.5 rounded border-gray-300 text-primary focus:ring-primary"
            />
            <label
              htmlFor="menu-broad-search"
              className="text-[11px] font-medium text-muted-foreground cursor-pointer select-none"
            >
              Inclure les mentions (recherche large)
            </label>
          </div>
        )}
      </div>

      <ScrollArea className="flex-1">
        <div className="p-2 space-y-0.5">
          <button
            type="button"
            onClick={() => {
              onSelectParticipant("");
              onSelectGroup("");
            }}
            className={cn(
              "flex items-center w-full px-2 py-2 text-sm rounded-md text-left transition-colors",
              selectedParticipant === "" && !selectedGroup
                ? "bg-primary/10 text-primary font-medium"
                : "hover:bg-accent text-foreground/80",
            )}
          >
            <div className="flex items-center gap-2 flex-1">
              <Globe className="h-4 w-4 opacity-70" />
              <span>Tous les participants</span>
            </div>
            {selectedParticipant === "" && !selectedGroup && (
              <Check className="h-4 w-4 shrink-0" />
            )}
          </button>

          {/* Groups as selectable ensembles */}
          {filteredGroupsInList.length > 0 && (
            <div className="mt-2 mb-1 px-2">
              <h3 className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
                Groupes
              </h3>
            </div>
          )}
          {filteredGroupsInList.map((group) => (
            <button
              type="button"
              key={`list-group-${group.id}`}
              onClick={() => {
                onSelectGroup(selectedGroup === group.id ? "" : group.id);
              }}
              className={cn(
                "flex items-center w-full px-2 py-2 text-sm rounded-md text-left transition-colors",
                selectedGroup === group.id
                  ? "bg-primary/10 text-primary font-medium"
                  : "hover:bg-accent text-foreground/80",
              )}
            >
              <div className="flex items-center gap-2 flex-1 min-w-0">
                <Users className="h-4 w-4 opacity-70 shrink-0" />
                <span className="truncate">{group.title}</span>
              </div>
              {selectedGroup === group.id && (
                <Check className="h-4 w-4 shrink-0" />
              )}
            </button>
          ))}

          {/* Individual Participants */}
          {filteredParticipants.length > 0 && (
            <div className="mt-2 mb-1 px-2">
              <h3 className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
                Participants
              </h3>
            </div>
          )}
          {filteredParticipants.map((name: string) => (
            <button
              type="button"
              key={name}
              onClick={() => {
                onSelectParticipant(selectedParticipant === name ? "" : name);
              }}
              className={cn(
                "flex items-center w-full px-2 py-2 text-sm rounded-md text-left transition-colors",
                selectedParticipant === name
                  ? "bg-primary/10 text-primary font-medium"
                  : "hover:bg-accent text-foreground/80",
              )}
            >
              <div className="flex items-center gap-2 flex-1 min-w-0">
                <User className="h-4 w-4 opacity-70 shrink-0" />
                <span className="truncate">{name}</span>
              </div>
              {selectedParticipant === name && (
                <Check className="h-4 w-4 shrink-0" />
              )}
            </button>
          ))}

          {filteredParticipants.length === 0 &&
            filteredGroupsInList.length === 0 && (
              <div className="p-8 text-center text-sm text-muted-foreground">
                Aucun résultat trouvé.
              </div>
            )}
        </div>
      </ScrollArea>
    </div>
  );
}
