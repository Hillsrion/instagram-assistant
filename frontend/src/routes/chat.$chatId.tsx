import { useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { FileText } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { ChatInput } from "@/components/ChatInput";
import { SourcesModal } from "@/components/SourcesModal";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useChatFilters } from "@/hooks/use-chat-filters";
import { useChatStream } from "@/hooks/use-chat-stream";
import { getConversation } from "@/lib/api";
import type { Source, SummarySource } from "@/lib/types";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/chat/$chatId")({
  validateSearch: (search: Record<string, unknown>) => {
    return {
      b: search.b === "true" || search.b === true || undefined,
    } as { q?: string; p?: string; g?: string; b?: boolean };
  },
  component: ChatRoute,
});

function ChatRoute() {
  const { chatId } = Route.useParams();
  const {
    q: initialMessage,
    p: initialParticipant,
    g: initialGroup,
    b: initialBroad,
  } = Route.useSearch();
  const scrollRef = useRef<HTMLDivElement>(null);

  const { data: conversation, isLoading } = useQuery({
    queryKey: ["conversation", chatId],
    queryFn: () => getConversation(chatId),
    refetchOnWindowFocus: false,
  });

  // Filters & Models Hook
  const {
    modelsData,
    participantNames,
    filterParticipant,
    setFilterParticipant,
    filterGroup,
    setFilterGroup,
    filterBroad,
    setFilterBroad,
    filterDate,
    setFilterDate,
    selectedModel,
    setSelectedModel,
  } = useChatFilters({
    initialParticipant,
    initialGroup,
    initialBroad,
  });

  // Chat hook
  const {
    messages,
    setMessages,
    sendMessage,
    isStreaming,
    streamStatus,
    stopStream,
  } = useChatStream({ chatId });

  // Sync with initial loaded messages
  useEffect(() => {
    if (conversation?.messages) {
      setMessages(conversation.messages);
    }
  }, [conversation, setMessages]);

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

  // Handle initial message from query param
  const initialProcessed = useRef(false);
  useEffect(() => {
    if (initialMessage && !initialProcessed.current && conversation) {
      initialProcessed.current = true;
      sendMessage(initialMessage, {
        participant: filterParticipant,
        group: filterGroup,
        broadSearch: filterBroad,
      });
    }
  }, [
    initialMessage,
    conversation,
    sendMessage,
    filterParticipant,
    filterGroup,
    filterBroad,
  ]);

  const [sourcesModalOpen, setSourcesModalOpen] = useState(false);
  const [selectedMessageSources, setSelectedMessageSources] = useState<{
    sources: Source[];
    summary_sources: SummarySource[];
  } | null>(null);

  const handleSendMessage = (content: string, options: any) => {
    sendMessage(content, {
      ...options,
      model: selectedModel,
      date: filterDate,
    });
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
          {/* biome-ignore lint/suspicious/noArrayIndexKey: order is stable */}
          {filteredMessages.map((msg, i) => (
            <div
              key={`${msg.role}-${msg.timestamp || i}`}
              className={cn(
                "flex",
                msg.role === "user" ? "justify-end" : "justify-start",
              )}
            >
              <div
                className={cn(
                  "flex flex-col gap-2",
                  msg.role === "user"
                    ? "max-w-[85%] items-end"
                    : "w-full items-start",
                )}
              >
                <div
                  className={cn(
                    "text-[15px] leading-relaxed",
                    msg.role === "user"
                      ? "rounded-2xl px-4 py-2 bg-primary text-primary-foreground shadow-sm text-sm"
                      : "py-1 text-foreground",
                  )}
                >
                  {msg.role === "assistant" ? (
                    <div className="prose dark:prose-invert max-w-none wrap-break-word">
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
        <div className="max-w-3xl mx-auto">
          <ChatInput
            onSendMessage={handleSendMessage}
            isStreaming={isStreaming}
            stopStream={stopStream}
            selectedModel={selectedModel || ""}
            setSelectedModel={setSelectedModel}
            modelsData={modelsData}
            filterParticipant={filterParticipant}
            setFilterParticipant={setFilterParticipant}
            filterGroup={filterGroup}
            setFilterGroup={setFilterGroup}
            filterBroad={filterBroad}
            setFilterBroad={setFilterBroad}
            filterDate={filterDate}
            setFilterDate={setFilterDate}
            participantNames={participantNames}
            isLoading={isLoading}
            autoFocus
          />
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
