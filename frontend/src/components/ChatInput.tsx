import { Send, SlidersHorizontal, Sparkles, StopCircle } from "lucide-react";
import { useRef } from "react";
import { SearchPopover } from "@/components/SearchPopover";
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
  participantNames: string[];
  className?: string;
  isLoading?: boolean;
  autoFocus?: boolean;
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
  participantNames,
  className,
  isLoading,
  autoFocus = false,
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
      });
      inputRef.current.value = "";
    }
  };

  return (
    <div className={cn("space-y-3", className)}>
      {/* Input */}
      <div className="flex gap-2 relative">
        <Input
          ref={inputRef}
          autoFocus={autoFocus}
          placeholder={
            filterParticipant
              ? `Ask a question about ${filterParticipant}...`
              : filterGroup
                ? `Ask a question about group ${filterGroup}...`
                : "Poser une question sur vos conversations..."
          }
          className="flex-1 pr-12 min-h-[50px] text-base shadow-sm"
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSubmit();
            }
          }}
          disabled={isStreaming}
        />

        <div className="absolute right-1.5 top-1.5">
          {isStreaming ? (
            <Button
              variant="destructive"
              size="icon"
              onClick={stopStream}
              className="h-9 w-9 rounded-full"
            >
              <StopCircle className="h-4 w-4" />
            </Button>
          ) : (
            <Button
              size="icon"
              onClick={() => handleSubmit()}
              disabled={isLoading}
              className="h-9 w-9 rounded-full"
            >
              <Send className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>

      {/* Toolbar: Filters & Model Selection */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {/* 1. FILTER POPOVER */}
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
              variant="outline"
              size="sm"
              className={cn(
                "gap-2 h-8 text-xs font-medium border-dashed",
                (filterParticipant || filterGroup) &&
                  "bg-primary/5 border-primary/20 text-primary border-solid",
              )}
            >
              <SlidersHorizontal className="h-3.5 w-3.5" />
              {filterParticipant ? (
                <span>
                  Personne:{" "}
                  <span className="font-semibold">{filterParticipant}</span>
                  {filterBroad && (
                    <span className="text-[10px] ml-1 opacity-70">(Large)</span>
                  )}
                </span>
              ) : filterGroup ? (
                <span>
                  Groupe: <span className="font-semibold">{filterGroup}</span>
                </span>
              ) : (
                "Filtres"
              )}
              {(filterParticipant || filterGroup) && (
                <Badge
                  variant="secondary"
                  className="ml-1 h-5 px-1 rounded-sm bg-primary/10 text-primary hover:bg-primary/20"
                >
                  1
                </Badge>
              )}
            </Button>
          </SearchPopover>

          {/* 2. MODEL SELECTOR */}
          {modelsData?.models && modelsData.models.length > 0 && (
            <Select
              value={selectedModel || modelsData.default_model || ""}
              onValueChange={setSelectedModel}
            >
              <SelectTrigger className="h-8 w-auto gap-2 text-xs border-0 bg-transparent hover:bg-muted/50 focus:ring-0 px-2 text-muted-foreground hover:text-foreground transition-all duration-300">
                <Sparkles className="h-3.5 w-3.5" />
                <SelectValue placeholder="Model" />
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
  );
}
