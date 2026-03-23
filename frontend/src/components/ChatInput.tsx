import { useQuery } from "@tanstack/react-query";
import { Instagram, Send, StopCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useChatInput } from "@/hooks/use-chat-input";
import { getAgents } from "@/lib/api/agents";
import type { ChatInputProps } from "@/lib/types";
import { cn } from "@/lib/utils";
import { ChatInputAgentPill } from "./chat-input/ChatInputAgentPill";
import { ChatInputPreviews } from "./chat-input/ChatInputPreviews";
import { ChatInputToolbar } from "./chat-input/ChatInputToolbar";

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
  selectedAgent,
  setSelectedAgent,
  className,
  isLoading,
  autoFocus = false,
  isHome = false,
}: ChatInputProps) {
  const {
    inputRef,
    attachments,
    isUploading,
    handleSubmit,
    handleFilesSelected,
    removeAttachment,
  } = useChatInput({
    onSendMessage,
    filterParticipant,
    filterGroup,
    filterBroad,
    selectedModel,
    selectedMode,
    filterDate,
  });

  const { data: agents = [] } = useQuery({
    queryKey: ["agents"],
    queryFn: getAgents,
  });

  const currentAgent = agents.find((a) => a.id === selectedAgent);
  const isAgentActive = selectedAgent !== "standard" && currentAgent;

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
      <div
        className={cn(
          "bg-card border rounded-2xl shadow-xl overflow-hidden transition-all duration-300 relative",
          isAgentActive
            ? "border-primary ring-1 ring-primary/20 shadow-primary/5"
            : "focus-within:ring-1 focus-within:ring-primary/20 focus-within:border-primary/30",
        )}
      >
        {isAgentActive && (
          <ChatInputAgentPill
            currentAgent={currentAgent}
            onDeactivate={() => setSelectedAgent("standard")}
          />
        )}

        <ChatInputPreviews
          attachments={attachments}
          isUploading={isUploading}
          onRemove={removeAttachment}
        />

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

        <ChatInputToolbar
          participantNames={participantNames}
          filterParticipant={filterParticipant}
          setFilterParticipant={setFilterParticipant}
          filterGroup={filterGroup}
          setFilterGroup={setFilterGroup}
          filterBroad={filterBroad}
          setFilterBroad={setFilterBroad}
          filterDate={filterDate}
          setFilterDate={setFilterDate}
          selectedAgent={selectedAgent}
          setSelectedAgent={setSelectedAgent}
          handleFilesSelected={handleFilesSelected}
          developerMode={developerMode}
          selectedModel={selectedModel}
          setSelectedModel={setSelectedModel}
          modelsData={modelsData}
          selectedMode={selectedMode}
          setSelectedMode={setSelectedMode}
        />
      </div>
    </div>
  );
}
