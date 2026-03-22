import { format } from "date-fns";
import { fr } from "date-fns/locale";
import {
  CalendarDays,
  Instagram,
  Plus,
  Send,
  Sparkles,
  StopCircle,
  Users,
} from "lucide-react";
import { useRef } from "react";
import type { DateRange } from "react-day-picker";
import { ChatInputMenu } from "@/components/ChatInputMenu";
import { type ChatMode, ModeSelector } from "@/components/ModeSelector";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";

interface ChatInputProps {
  onSendMessage: (
    content: string,
    options: {
      participant?: string;
      group?: string;
      broadSearch?: boolean;
      model?: string;
      mode?: string;
      date?: DateRange;
    },
  ) => void;
  isStreaming: boolean;
  stopStream: () => void;
  selectedModel: string;
  setSelectedModel: (model: string) => void;
  selectedMode: ChatMode;
  setSelectedMode: (mode: ChatMode) => void;
  developerMode: boolean;
  modelsData?: {
    models: Array<{ name: string }>;
    default_model: string;
  };
  filterParticipant: string;
  setFilterParticipant: (p: string) => void;
  filterGroup: string;
  setFilterGroup: (g: string) => void;
  filterBroad: boolean;
  setFilterBroad: (b: boolean) => void;
  filterDate?: DateRange;
  setFilterDate: (date: DateRange | undefined) => void;
  participantNames: string[];
  className?: string;
  isLoading?: boolean;
  autoFocus?: boolean;
  isHome?: boolean;
}

export function ChatInput({
  onSendMessage,
  isStreaming,
  stopStream,
  selectedModel,
  setSelectedModel,
  selectedMode,
  setSelectedMode,
  developerMode,
  modelsData,
  filterParticipant,
  setFilterParticipant,
  filterGroup,
  setFilterGroup,
  filterBroad,
  setFilterBroad,
  filterDate,
  setFilterDate,
  participantNames,
  className,
  isLoading,
  autoFocus = false,
  isHome = false,
}: ChatInputProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  const handleSubmit = (e?: React.FormEvent) => {
    e?.preventDefault();
    if (inputRef.current?.value) {
      onSendMessage(inputRef.current.value, {
        participant: filterParticipant,
        group: filterGroup,
        broadSearch: filterBroad,
        model: selectedModel,
        mode: selectedMode,
        date: filterDate,
      });
      inputRef.current.value = "";
    }
  };

  const selectedCount = (filterParticipant ? 1 : 0) + (filterGroup ? 1 : 0);

  return (
    <div
      className={cn(
        "w-full transition-all duration-700 ease-in-out",
        isHome
          ? "fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-50 p-4 max-w-2xl animate-in fade-in zoom-in-95 duration-700"
          : "relative p-0",
        className,
      )}
      style={{
        viewTransitionName: "chat-input",
      }}
    >
      {isHome && (
        <div className="flex flex-col items-center gap-12 mb-10 text-center animate-in fade-in slide-in-from-bottom-8 duration-1000 ease-out">
          <div className="h-16 w-16 rounded-2xl bg-primary/10 flex items-center justify-center border border-primary/20 shadow-sm">
            <Instagram className="h-10 w-10 text-primary" />
          </div>
        </div>
      )}
      <div className="bg-card border rounded-2xl shadow-xl overflow-hidden focus-within:ring-1 focus-within:ring-primary/20 focus-within:border-primary/30 transition-all duration-300">
        {/* Unified Container Input Area */}
        <div className="flex gap-2 relative p-2 px-3">
          <Input
            ref={inputRef}
            autoFocus={autoFocus}
            placeholder={
              filterParticipant
                ? `Demander quelque chose sur ${filterParticipant}...`
                : filterGroup
                  ? `Demander quelque chose sur le groupe ${filterGroup}...`
                  : "Quels ont été les moments forts de mes conversations avec Marie ?"
            }
            className="flex-1 border-0 shadow-none focus-visible:ring-0 text-base min-h-[44px] bg-transparent"
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSubmit();
              }
            }}
            disabled={isStreaming}
          />

          <div className="flex items-center">
            {isStreaming ? (
              <Button
                variant="destructive"
                size="icon"
                onClick={stopStream}
                className="h-8 w-8 rounded-full"
              >
                <StopCircle className="h-4 w-4" />
              </Button>
            ) : (
              <Button
                size="icon"
                onClick={() => handleSubmit()}
                disabled={isLoading}
                className="h-8 w-8 rounded-full"
              >
                <Send className="h-4 w-4" />
              </Button>
            )}
          </div>
        </div>

        {/* Toolbar: Inside the rounded container */}
        <div className="flex items-center justify-between px-3 pb-2 border-t border-muted/30 pt-2 bg-muted/5">
          <div className="flex items-center gap-1.5">
            {/* 1. CHAT INPUT MENU */}
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

            {/* 3. MODE OR MODEL SELECTOR */}
            {developerMode ? (
              // Developer Mode: Show Model Selector
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
              // Regular Mode: Show Mode Selector
              <ModeSelector
                mode={selectedMode}
                onModeChange={setSelectedMode}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
