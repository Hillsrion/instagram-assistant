import { format } from "date-fns";
import { fr } from "date-fns/locale";
import {
  CalendarDays,
  Instagram,
  Send,
  SlidersHorizontal,
  Sparkles,
  StopCircle,
} from "lucide-react";
import { useRef } from "react";
import type { DateRange } from "react-day-picker";
import { SearchPopover } from "@/components/SearchPopover";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Input } from "@/components/ui/input";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
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
      date?: DateRange;
    },
  ) => void;
  isStreaming: boolean;
  stopStream: () => void;
  selectedModel: string;
  setSelectedModel: (model: string) => void;
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
            {/* 1. COMPTES POPOVER (Renamed from Filters) */}
            <SearchPopover
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
            >
              <Button
                variant="ghost"
                size="sm"
                className={cn(
                  "gap-1.5 h-7 text-xs font-medium hover:bg-muted transition-colors rounded-lg",
                  selectedCount > 0 &&
                    "bg-primary/5 text-primary hover:bg-primary/10",
                )}
              >
                <SlidersHorizontal className="h-3 w-3" />
                <span>
                  {selectedCount > 0
                    ? `${selectedCount} compte${selectedCount > 1 ? "s" : ""}`
                    : "Comptes"}
                </span>
              </Button>
            </SearchPopover>

            {/* 2. DATEPICKER */}
            <Popover>
              <PopoverTrigger asChild>
                <Button
                  variant="ghost"
                  size="sm"
                  className={cn(
                    "gap-1.5 h-7 text-xs font-medium hover:bg-muted transition-colors rounded-lg",
                    filterDate?.from &&
                      "bg-primary/5 text-primary hover:bg-primary/10",
                  )}
                >
                  <CalendarDays className="h-3 w-3" />
                  <span>
                    {filterDate?.from ? (
                      filterDate.to ? (
                        <>
                          {format(filterDate.from, "d MMM", { locale: fr })} -{" "}
                          {format(filterDate.to, "d MMM yyyy", { locale: fr })}
                        </>
                      ) : (
                        format(filterDate.from, "d MMM yyyy", { locale: fr })
                      )
                    ) : (
                      "Date"
                    )}
                  </span>
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-auto p-0" align="start">
                <Calendar
                  mode="range"
                  selected={filterDate}
                  onSelect={setFilterDate}
                  initialFocus
                  locale={fr}
                  numberOfMonths={2}
                  className="p-4"
                />
              </PopoverContent>
            </Popover>

            {/* 3. MODEL SELECTOR */}
            {modelsData?.models && modelsData.models.length > 0 && (
              <Select
                value={selectedModel || modelsData.default_model || ""}
                onValueChange={setSelectedModel}
              >
                <SelectTrigger className="h-7 w-auto gap-1.5 text-xs border-0 bg-transparent hover:bg-muted focus:ring-0 px-2 text-muted-foreground hover:text-foreground transition-all duration-300 rounded-lg">
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
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
