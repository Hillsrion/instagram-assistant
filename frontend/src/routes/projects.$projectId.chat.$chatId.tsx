import { useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { FileText } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { DateRange } from "react-day-picker";
import ReactMarkdown from "react-markdown";
import { Breadcrumbs, ProjectMenu } from "@/components/Breadcrumbs";
import { ChatInput } from "@/components/ChatInput";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useChatFilters } from "@/hooks/use-chat-filters";
import { useChatStream } from "@/hooks/use-chat-stream";
import { getConversation, getProject } from "@/lib/api";
import type { FileAttachment } from "@/lib/types";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/projects/$projectId/chat/$chatId")({
  component: ProjectChat,
});

function ProjectChat() {
  const { projectId, chatId } = Route.useParams();
  const scrollRef = useRef<HTMLDivElement>(null);

  const { data: project } = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => getProject(projectId),
  });

  const { data: conversation, isLoading } = useQuery({
    queryKey: ["conversation", chatId],
    queryFn: () => getConversation(chatId),
  });

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
  } = useChatFilters();

  const [selectedAgent, setSelectedAgent] = useState("standard");

  const {
    messages,
    setMessages,
    sendMessage,
    isStreaming,
    streamStatus,
    stopStream,
  } = useChatStream({ chatId });

  useEffect(() => {
    if (conversation?.messages) {
      setMessages(conversation.messages);
    }
  }, [conversation, setMessages]);

  const filteredMessages = useMemo(() => {
    return messages;
  }, [messages]);

  const handleSendMessage = (
    content: string,
    options: {
      participant?: string;
      group?: string;
      broadSearch?: boolean;
      model?: string;
      date?: DateRange;
      attachments?: FileAttachment[];
    },
  ) => {
    sendMessage(content, {
      ...options,
      model: selectedModel || options.model,
      date: filterDate || options.date,
    });
  };

  return (
    <div className="flex flex-col h-full bg-white relative">
      <header className="flex items-center justify-between px-6 py-4 border-b bg-white z-10 h-14 shrink-0">
        {project && (
          <Breadcrumbs
            project={project}
            conversation={conversation}
            showMenu={false}
          />
        )}
        {project && <ProjectMenu project={project} />}
      </header>

      <ScrollArea className="flex-1 p-4">
        <div className="max-w-3xl mx-auto space-y-6 pb-32">
          {filteredMessages.map((msg, i) => {
            const messageKey = msg.timestamp
              ? `${msg.role}-${msg.timestamp}-${i}`
              : `${msg.role}-${i}`;
            return (
              <div
                key={messageKey}
                className={cn(
                  "flex flex-col gap-1",
                  msg.role === "user" ? "items-end" : "items-start",
                )}
              >
                {/* Attachments (separate visual bubbles) */}
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
                          file.type === "image" ? "w-40 h-40" : "w-32 h-24",
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
                      "max-w-[85%] rounded-2xl px-4 py-2",
                      msg.role === "user"
                        ? "bg-primary text-primary-foreground text-sm shadow-sm"
                        : "bg-transparent text-foreground",
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
                )}
              </div>
            );
          })}

          {isStreaming && (
            <div className="flex items-center gap-2 text-xs text-muted-foreground animate-pulse">
              <div className="h-2 w-2 rounded-full bg-primary animate-bounce" />
              {streamStatus}
            </div>
          )}
          <div ref={scrollRef} />
        </div>
      </ScrollArea>

      <div className="absolute bottom-0 left-0 right-0 p-6 bg-linear-to-t from-white via-white/90 to-transparent">
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
            selectedAgent={selectedAgent}
            setSelectedAgent={setSelectedAgent}
            isLoading={isLoading}
            autoFocus
          />
        </div>
      </div>
    </div>
  );
}
