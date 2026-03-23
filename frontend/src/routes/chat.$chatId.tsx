import { useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { ArrowRight, FileText } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ChatInput } from "@/components/ChatInput";
import { ConversationMenu } from "@/components/ConversationMenu";
import { SourcesModal } from "@/components/SourcesModal";
import { TypingIndicator } from "@/components/TypingIndicator";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useChatFilters } from "@/hooks/use-chat-filters";
import { useChatStream } from "@/hooks/use-chat-stream";
import { getConversation } from "@/lib/api";
import type { Source, SummarySource } from "@/lib/types";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/chat/$chatId")({
  validateSearch: (search: Record<string, unknown>) => {
    return {
      q: typeof search.q === "string" ? search.q : undefined,
      p: typeof search.p === "string" ? search.p : undefined,
      g: typeof search.g === "string" ? search.g : undefined,
      b: search.b === "true" || search.b === true || undefined,
      m: typeof search.m === "string" ? search.m : undefined,
      at: typeof search.at === "string" ? search.at : undefined,
    } as {
      q?: string;
      p?: string;
      g?: string;
      b?: boolean;
      m?: "fast" | "reflexion";
      at?: string;
    };
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
    m: initialMode,
    at: initialAttachmentsId,
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
    selectedMode,
    setSelectedMode,
    developerMode,
  } = useChatFilters({
    initialParticipant,
    initialGroup,
    initialBroad,
    initialMode,
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
        model: selectedModel, // Ensure initial message uses selected model
        mode: selectedMode, // Ensure initial message uses selected mode
        attachments: initialAttachmentsId
          ? JSON.parse(initialAttachmentsId)
          : undefined,
      });
    }
  }, [
    initialMessage,
    conversation,
    sendMessage,
    filterParticipant,
    filterGroup,
    filterBroad,
    selectedModel,
    selectedMode,
    initialAttachmentsId,
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
      mode: selectedMode, // Pass selectedMode to sendMessage
    });
  };

  return (
    <div className="flex h-full flex-col relative bg-gray-50/50">
      {/* Header - SIMPLIFIED */}
      <div className="p-4 pl-8 flex items-center justify-between backdrop-blur z-10 w-full h-14 bg-background/50">
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
        {conversation && (
          <ConversationMenu
            conversation={{
              id: conversation.id,
              title: conversation.title,
              is_favorite: !!conversation.is_favorite,
            }}
          />
        )}
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
                {/* Attachments (as separate bubbles/messages) */}
                {msg.attachments && msg.attachments.length > 0 && (
                  <div
                    className={cn(
                      "flex flex-wrap gap-2 mb-1",
                      msg.role === "user" ? "justify-end" : "justify-start",
                    )}
                  >
                    {msg.attachments.map((file) => (
                      <div
                        key={file.id}
                        className={cn(
                          "relative rounded-2xl border bg-background/50 overflow-hidden flex items-center justify-center shadow-sm hover:shadow-md transition-all duration-200 border-muted/20 hover:border-primary/20 group",
                          file.type === "image" ? "w-48 h-48" : "w-32 h-24",
                        )}
                      >
                        {file.type === "image" ? (
                          <img
                            src={file.url}
                            alt={file.name}
                            className="w-full h-full object-cover cursor-pointer hover:opacity-90 transition-opacity group-hover:scale-105 duration-500"
                            onClick={() => window.open(file.url, "_blank")}
                          />
                        ) : (
                          <div
                            className="flex flex-col items-center gap-1.5 p-3 text-[10px] text-center cursor-pointer hover:bg-muted/50 transition-colors w-full h-full justify-center"
                            onClick={() => window.open(file.url, "_blank")}
                          >
                            <div className="p-2 bg-muted/30 rounded-lg group-hover:bg-primary/10 transition-colors">
                              <FileText className="h-6 w-6 text-muted-foreground group-hover:text-primary transition-colors" />
                            </div>
                            <span className="truncate w-24 text-foreground/80 font-medium">
                              {file.name}
                            </span>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                {msg.content && (
                  <div
                    className={cn(
                      "text-[15px] leading-relaxed",
                      msg.role === "user"
                        ? "rounded-2xl px-4 py-2 bg-primary text-primary-foreground shadow-sm text-sm"
                        : "py-1 text-foreground",
                    )}
                  >
                    {msg.role === "assistant" ? (
                      <div className="prose dark:prose-invert max-w-none wrap-break-word font-normal">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {msg.content}
                        </ReactMarkdown>
                      </div>
                    ) : (
                      <div className="whitespace-pre-wrap">{msg.content}</div>
                    )}
                  </div>
                )}

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

                {/* Followups */}
                {msg.followups && msg.followups.length > 0 && (
                  <div className="flex flex-col gap-1 mt-3 w-full">
                    {msg.followups.map((followup, idx) => (
                      <button
                        key={idx}
                        type="button"
                        onClick={() =>
                          handleSendMessage(followup, {
                            participant: filterParticipant,
                            group: filterGroup,
                            broadSearch: filterBroad,
                          })
                        }
                        className="group flex items-center gap-2 text-[13px] text-muted-foreground hover:text-primary transition-colors text-left py-1 w-full"
                      >
                        <ArrowRight className="h-3.5 w-3.5 text-primary/40 group-hover:text-primary transition-colors shrink-0" />
                        <span className="flex-1">{followup}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}

          {/* Stream Status Indicator */}
          {isStreaming && (
            <div className="flex items-center gap-3 text-[13px] text-muted-foreground animate-pulse font-medium">
              <TypingIndicator />
              <span>{streamStatus}</span>
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
            selectedMode={selectedMode}
            setSelectedMode={setSelectedMode}
            developerMode={developerMode}
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
