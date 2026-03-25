import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { ChatInput } from "@/components/ChatInput";
import { useChatFilters } from "@/hooks/use-chat-filters";
import { createChat } from "@/lib/api";

export const Route = createFileRoute("/")({
  component: Index,
});

function Index() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

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
  } = useChatFilters();

  const createMutation = useMutation({
    mutationFn: (title?: string) => createChat(title),
  });

  const [selectedAgent, setSelectedAgent] = useState("standard");

  const handleSendMessage = async (content: string, options: any) => {
    try {
      const newChat = (await createMutation.mutateAsync(
        content.slice(0, 30) + (content.length > 30 ? "..." : ""),
      )) as any;

      // Navigate to chat with initial message and filters
      navigate({
        to: "/chat/$chatId",
        params: { chatId: newChat.id },
        search: {
          q: content,
          p: options.participant || undefined,
          g: options.group || undefined,
          b: options.broadSearch || undefined,
          m: options.mode || undefined,
          at: options.attachments
            ? JSON.stringify(options.attachments)
            : undefined,
        },
      });

      // Delay invalidation to avoid flickering during the view transition
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ["chats"] });
      }, 500);
    } catch (error) {
      console.error("Failed to create chat:", error);
    }
  };

  return (
    <div className="flex h-full flex-col items-center justify-center bg-gray-50/50 px-4">
      <div className="w-full max-w-2xl space-y-8 -translate-y-12 animate-in fade-in slide-in-from-bottom-4 duration-700">
        {/* Centered Chat Input */}
        <div className="h-[60px] w-full flex items-center justify-center">
          <ChatInput
            onSendMessage={(content, options) => {
              handleSendMessage(content, options);
            }}
            isStreaming={false}
            stopStream={() => {}}
            selectedModel={selectedModel}
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
            isLoading={createMutation.isPending}
            autoFocus
            isHome
          />
        </div>

        {/* Suggested Actions or Info */}
        <div className="flex flex-wrap justify-center gap-2 pt-4 opacity-70">
          <p className="text-xs text-muted-foreground w-full text-center mb-1">
            Recherchez des thèmes, des sentiments ou des résumés.
          </p>
        </div>
      </div>
    </div>
  );
}
