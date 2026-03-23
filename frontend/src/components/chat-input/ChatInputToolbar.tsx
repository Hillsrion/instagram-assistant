import { format } from "date-fns";
import { fr } from "date-fns/locale";
import { CalendarDays, Plus, Sparkles, Users } from "lucide-react";
import type { DateRange } from "react-day-picker";
import { ChatInputMenu } from "@/components/ChatInputMenu";
import { type ChatMode, ModeSelector } from "@/components/ModeSelector";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";

interface ChatInputToolbarProps {
  participantNames: string[];
  filterParticipant: string;
  setFilterParticipant: (p: string) => void;
  filterGroup: string;
  setFilterGroup: (g: string) => void;
  filterBroad: boolean;
  setFilterBroad: (b: boolean) => void;
  filterDate?: DateRange;
  setFilterDate: (date: DateRange | undefined) => void;
  selectedAgent: string;
  setSelectedAgent: (id: string) => void;
  handleFilesSelected: (files: FileList) => void;
  developerMode: boolean;
  selectedModel: string;
  setSelectedModel: (model: string) => void;
  modelsData?: {
    models: Array<{ name: string }>;
    default_model: string;
  };
  selectedMode: ChatMode;
  setSelectedMode: (mode: ChatMode) => void;
}

export function ChatInputToolbar({
  participantNames,
  filterParticipant,
  setFilterParticipant,
  filterGroup,
  setFilterGroup,
  filterBroad,
  setFilterBroad,
  filterDate,
  setFilterDate,
  selectedAgent,
  setSelectedAgent,
  handleFilesSelected,
  developerMode,
  selectedModel,
  setSelectedModel,
  modelsData,
  selectedMode,
  setSelectedMode,
}: ChatInputToolbarProps) {
  const selectedCount = (filterParticipant ? 1 : 0) + (filterGroup ? 1 : 0);

  return (
    <div className="flex items-center justify-between px-3 pb-2 border-t border-muted/30 pt-2 bg-muted/5">
      <div className="flex items-center gap-1.5">
        <ChatInputMenu
          participantNames={participantNames}
          selectedParticipant={filterParticipant}
          onSelectParticipant={(p) => {
            setFilterParticipant(p);
            if (p) setFilterGroup("");
            if (!p) setFilterBroad(false);
          }}
          isBroadSearch={filterBroad}
          onBroadSearchChange={setFilterBroad}
          selectedGroup={filterGroup}
          onSelectGroup={(g) => {
            setFilterGroup(g);
            if (g) {
              setFilterParticipant("");
              setFilterBroad(false);
            }
          }}
          filterDate={filterDate}
          setFilterDate={setFilterDate}
          onReset={() => {
            setFilterParticipant("");
            setFilterGroup("");
            setFilterBroad(false);
            setFilterDate(undefined);
          }}
          onFilesSelected={handleFilesSelected}
          selectedAgent={selectedAgent}
          onSelectAgent={setSelectedAgent}
        >
          <Button
            variant="outline"
            size="sm"
            className={cn(
              "gap-1.5 h-7 w-7 p-0 rounded-lg text-muted-foreground hover:text-foreground transition-colors",
              selectedCount > 0 || filterDate?.from
                ? "border-primary/50 text-primary hover:text-primary hover:bg-primary/10"
                : "border-dashed hover:border-solid",
            )}
          >
            <Plus className="h-4 w-4" />
          </Button>
        </ChatInputMenu>

        {/* Selected Filters Badges */}
        {selectedCount > 0 && (
          <Badge
            variant="secondary"
            className="h-6 px-2 text-[10px] font-medium bg-primary/10 text-primary hover:bg-primary/20 cursor-default"
          >
            <Users className="h-3 w-3 mr-1" />
            {selectedCount} compte{selectedCount > 1 ? "s" : ""}
          </Badge>
        )}

        {filterDate?.from && (
          <Badge
            variant="secondary"
            className="h-6 px-2 text-[10px] font-medium bg-primary/10 text-primary hover:bg-primary/20 cursor-default"
          >
            <CalendarDays className="h-3 w-3 mr-1" />
            {filterDate.to
              ? `${format(filterDate.from, "d MMM", { locale: fr })} - ${format(filterDate.to, "d MMM yy", { locale: fr })}`
              : format(filterDate.from, "d MMM yyyy", { locale: fr })}
          </Badge>
        )}

        {developerMode ? (
          modelsData?.models &&
          modelsData.models.length > 0 && (
            <Select
              value={selectedModel || modelsData.default_model || ""}
              onValueChange={setSelectedModel}
            >
              <SelectTrigger className="h-7 w-auto gap-1.5 text-xs font-medium border-0 bg-transparent hover:bg-muted focus:ring-0 px-2 transition-all duration-300 rounded-lg focus-visible:ring-0">
                <Sparkles className="h-3 w-3" />
                <SelectValue placeholder="Modèle" />
              </SelectTrigger>
              <SelectContent>
                {modelsData.models.map((model) => (
                  <SelectItem
                    key={model.name}
                    value={model.name}
                    className="text-xs"
                  >
                    {model.name.includes(":")
                      ? model.name
                      : `${model.name}:latest`}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )
        ) : (
          <ModeSelector mode={selectedMode} onModeChange={setSelectedMode} />
        )}
      </div>
    </div>
  );
}
