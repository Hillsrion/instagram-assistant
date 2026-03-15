import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { Instagram } from "lucide-react";
import { ChatInput } from "@/components/ChatInput";
import { useChatFilters } from "@/hooks/use-chat-filters";
import { createConversation } from "@/lib/api";

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
    selectedModel,
    setSelectedModel,
  } = useChatFilters();

  const createMutation = useMutation({
    mutationFn: (title?: string) => createConversation(title),
  });

  const handleSendMessage = async (content: string, options: any) => {
    try {
      const newConv = await createMutation.mutateAsync(
        content.slice(0, 30) + (content.length > 30 ? "..." : ""),
      );
      queryClient.invalidateQueries({ queryKey: ["conversations"] });

      // Navigate to chat with initial message and filters
      navigate({
        to: "/chat/$chatId",
        params: { chatId: newConv.id },
        search: {
          q: content,
          p: options.participant || undefined,
          g: options.group || undefined,
          b: options.broadSearch || undefined,
        },
      });
    } catch (error) {
      console.error("Failed to create conversation:", error);
    }
  };

  return (
    <div className="flex h-full flex-col items-center justify-center bg-gray-50/50 px-4">
      <div className="w-full max-w-2xl space-y-8 -translate-y-12 animate-in fade-in slide-in-from-bottom-4 duration-700">
        {/* Logo/Branding */}
        <div className="flex flex-col items-center gap-4 text-center">
          <div className="h-16 w-16 rounded-2xl bg-primary/10 flex items-center justify-center border border-primary/20 shadow-sm">
            <Instagram className="h-10 w-10 text-primary" />
          </div>
          <div className="space-y-1">
            <h1 className="text-3xl font-bold tracking-tight">
              Instagram Assistant
            </h1>
            <p className="text-muted-foreground">
              Analysez vos conversations Instagram avec l'IA locale.
            </p>
          </div>
        </div>

        {/* Centered Chat Input */}
        <div className="h-[60px] w-full flex items-center justify-center">
          <ChatInput
            onSendMessage={handleSendMessage}
            isStreaming={createMutation.isPending}
            stopStream={() => {}}
            selectedModel={selectedModel}
            setSelectedModel={setSelectedModel}
            modelsData={modelsData}
            filterParticipant={filterParticipant}
            setFilterParticipant={setFilterParticipant}
            filterGroup={filterGroup}
            setFilterGroup={setFilterGroup}
            filterBroad={filterBroad}
            setFilterBroad={setFilterBroad}
            participantNames={participantNames}
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
