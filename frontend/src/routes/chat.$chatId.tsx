import { useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import {
  FileText,
  Send,
  SlidersHorizontal,
  Sparkles,
  StopCircle,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { SearchPopover } from "@/components/SearchPopover"; // NEW IMPORT
import { SourcesModal } from "@/components/SourcesModal";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useChatStream } from "@/hooks/use-chat-stream";
import { getConversation, getOllamaModels, getParticipants } from "@/lib/api";
import type { Source, SummarySource } from "@/lib/types";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/chat/$chatId")({
  component: ChatRoute,
});

function ChatRoute() {
  const { chatId } = Route.useParams();
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const { data: conversation, isLoading } = useQuery({
    queryKey: ["conversation", chatId],
    queryFn: () => getConversation(chatId),
    refetchOnWindowFocus: false,
  });

  // Load available models
  const { data: modelsData } = useQuery({
    queryKey: ["ollama-models"],
    queryFn: () => getOllamaModels(),
    refetchOnWindowFocus: false,
  });

  // Load participants for filter
  const { data: participantsData } = useQuery({
    queryKey: ["participants"],
    queryFn: () => getParticipants(),
    refetchOnWindowFocus: false,
  });

  const participantNames = useMemo(() => {
    return participantsData?.map((p) => p.name) || [];
  }, [participantsData]);

  // Chat hook
  const {
    messages,
    setMessages,
    sendMessage,
    isStreaming,
    streamStatus,
    stopStream,
    selectedModel,
    setSelectedModel,
  } = useChatStream({ chatId });

  // Sync with initial loaded messages
  useEffect(() => {
    if (conversation?.messages) {
      setMessages(conversation.messages);
    }
  }, [conversation, setMessages]);

  // Set default model when models are loaded
  useEffect(() => {
    if (modelsData?.default_model && !selectedModel) {
      setSelectedModel(modelsData.default_model);
    }
  }, [modelsData, selectedModel, setSelectedModel]);

  // Filters State
  const [filterParticipant, setFilterParticipant] = useState<string>("");
  const [filterGroup, setFilterGroup] = useState<string>("");
  const [filterBroad, setFilterBroad] = useState<boolean>(false); // NEW

  // Filter Logic
  const filteredMessages = useMemo(() => {
    return messages.filter((msg) => {
      // User messages are always shown
      if (msg.role === "user") return true;

      // Participant Filter (Strict only for UI rendering)
      if (filterParticipant && !filterBroad) {
        // Modified: only strict if not broad
        // If it's an assistant message, we show it if:
        // 1. It has NO sources (likely a "not found" or general message)
        // 2. OR one of its sources contains the filtered participant

        const hasSources =
          (msg.sources && msg.sources.length > 0) ||
          (msg.summary_sources && msg.summary_sources.length > 0);

        if (!hasSources) {
          return true; // Show "not found" or error messages
        }

        const normalizedFilter = filterParticipant.toLowerCase();

        const hasParticipantInSources = msg.sources?.some((s) =>
          s.participants.some((p) =>
            p.toLowerCase().includes(normalizedFilter),
          ),
        );

        const hasParticipantInSummarySources = msg.summary_sources?.some((s) =>
          s.participants.some((p) =>
            p.toLowerCase().includes(normalizedFilter),
          ),
        );

        return !!(hasParticipantInSources || hasParticipantInSummarySources);
      }

      return true;
    });
  }, [messages, filterParticipant, filterBroad]);

  // Auto-scroll
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, []);

  const [sourcesModalOpen, setSourcesModalOpen] = useState(false);
  const [selectedMessageSources, setSelectedMessageSources] = useState<{
    sources: Source[];
    summary_sources: SummarySource[];
  } | null>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (inputRef.current?.value) {
      sendMessage(inputRef.current.value, {
        participant: filterParticipant,
        group: filterGroup,
        broadSearch: filterBroad, // NEW
      });
      inputRef.current.value = "";
    }
  };

  return (
    <div className="flex h-full flex-col relative bg-gray-50/50">
      {/* Header - SIMPLIFIED */}
      <div className="p-4 pl-8 flex items-center justify-between backdrop-blur z-10 w-full h-14">
        <div className="flex items-center gap-2">
          <h2 className="font-medium truncate max-w-[500px]">
            {conversation?.title || "Chat"}
          </h2>
          {isLoading && (
            <span className="text-xs text-muted-foreground animate-pulse">
              Loading...
            </span>
          )}
        </div>
      </div>

      {/* Messages Area */}
      <ScrollArea className="flex-1 p-4">
        <div className="max-w-3xl mx-auto space-y-6 pb-4">
          {filteredMessages.map((msg, i) => (
            <div
              key={msg.timestamp || i}
              className={cn(
                "flex",
                msg.role === "user" ? "justify-end" : "justify-start",
              )}
            >
              <div
                className={cn(
                  "flex flex-col gap-2 max-w-[80%]",
                  msg.role === "user" ? "items-end" : "items-start",
                )}
              >
                <div
                  className={cn(
                    "rounded-lg px-4 py-3 text-sm shadow-sm",
                    msg.role === "user"
                      ? "bg-primary text-primary-foreground"
                      : "bg-card border",
                  )}
                >
                  {msg.role === "assistant" ? (
                    <div className="prose dark:prose-invert prose-sm max-w-none wrap-break-word leading-relaxed">
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    </div>
                  ) : (
                    <div className="whitespace-pre-wrap">{msg.content}</div>
                  )}
                </div>

                {/* Sources */}
                {((msg.sources && msg.sources.length > 0) ||
                  (msg.summary_sources && msg.summary_sources.length > 0)) && (
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedMessageSources({
                        sources: msg.sources || [],
                        summary_sources: msg.summary_sources || [],
                      });
                      setSourcesModalOpen(true);
                    }}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-muted hover:bg-muted/80 text-muted-foreground hover:text-foreground text-xs font-medium transition-colors mt-1"
                  >
                    <FileText className="h-3 w-3" />
                    {(msg.sources?.length || 0) +
                      (msg.summary_sources?.length || 0)}{" "}
                    sources
                  </button>
                )}
              </div>
            </div>
          ))}

          {/* Stream Status Indicator */}
          {isStreaming && (
            <div className="flex items-center gap-2 text-xs text-muted-foreground animate-pulse">
              <div className="h-2 w-2 rounded-full bg-primary animate-bounce" />
              {streamStatus}
            </div>
          )}

          <div ref={scrollRef} />
        </div>
      </ScrollArea>

      {/* Input Area & Toolbar */}
      <div className="p-4 bg-background/95 backdrop-blur supports-backdrop-filter:bg-background/60">
        <div className="max-w-3xl mx-auto space-y-3">
          {/* Input */}
          <div className="flex gap-2 relative">
            <Input
              ref={inputRef}
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
                  handleSubmit(e);
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
                  onClick={handleSubmit}
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
                  if (!p) setFilterBroad(false); // Reset broad if no participant
                }}
                isBroadSearch={filterBroad} // NEW
                onBroadSearchChange={setFilterBroad} // NEW
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
                        <span className="text-[10px] ml-1 opacity-70">
                          (Large)
                        </span>
                      )}
                    </span>
                  ) : filterGroup ? (
                    <span>
                      Groupe:{" "}
                      <span className="font-semibold">{filterGroup}</span>
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

              {/* 2. MODEL SELECTOR (Moved here) */}
              {modelsData?.models && modelsData.models.length > 0 && (
                <Select
                  value={selectedModel || modelsData.default_model || ""}
                  onValueChange={setSelectedModel}
                >
                  <SelectTrigger className="h-8 w-auto gap-2 text-xs border-0 bg-transparent hover:bg-muted/50 focus:ring-0 px-2 text-muted-foreground hover:text-foreground transition-colors">
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
      </div>

      {/* Sources Modal */}
      {selectedMessageSources && (
        <SourcesModal
          sources={selectedMessageSources.sources}
          summarySources={selectedMessageSources.summary_sources}
          open={sourcesModalOpen}
          onOpenChange={setSourcesModalOpen}
        />
      )}
    </div>
  );
}
