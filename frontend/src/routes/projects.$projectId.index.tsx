import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { MessageSquare } from "lucide-react";
import { useState } from "react";
import { Breadcrumbs, ProjectMenu } from "@/components/Breadcrumbs";
import { ChatInput } from "@/components/ChatInput";
import { useChatFilters } from "@/hooks/use-chat-filters";
import { createChat, getProject, getProjectChats } from "@/lib/api";
import type { ChatListResponse } from "@/lib/types";

export const Route = createFileRoute("/projects/$projectId/")({
  component: ProjectIndex,
});

function ProjectIndex() {
  const { projectId } = Route.useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: project, isLoading: isProjectLoading } = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => getProject(projectId),
  });

  const { data: chats, isLoading: isChatsLoading } = useQuery({
    queryKey: ["project-chats", projectId],
    queryFn: () => getProjectChats(projectId),
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

  const createMutation = useMutation({
    mutationFn: (title?: string) => createChat(title, projectId),
  });

  const handleSendMessage = async (content: string, options: any) => {
    try {
      const newChat = (await createMutation.mutateAsync(
        content.slice(0, 30) + (content.length > 30 ? "..." : ""),
      )) as any;

      navigate({
        to: "/projects/$projectId/chat/$chatId",
        params: { projectId, chatId: newChat.id },
        search: {
          q: content,
          p: options.participant || undefined,
          g: options.group || undefined,
          b: options.broadSearch || undefined,
        },
      });

      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ["chats"] });
        queryClient.invalidateQueries({
          queryKey: ["project-chats", projectId],
        });
      }, 500);
    } catch (error) {
      console.error("Failed to create chat:", error);
    }
  };

  if (isProjectLoading)
    return (
      <div className="p-8 text-center text-slate-500">
        Chargement du projet...
      </div>
    );
  if (!project)
    return (
      <div className="p-8 text-center text-destructive">Projet non trouvé</div>
    );

  return (
    <div className="flex flex-col h-full bg-white relative">
      <header className="flex items-center justify-between px-6 py-4 border-b bg-white z-10">
        <Breadcrumbs project={project} showMenu={false} />
        <ProjectMenu project={project} />
      </header>

      <main className="flex-1 overflow-y-auto px-6 py-12">
        <div className="max-w-4xl mx-auto space-y-12 pb-32">
          <div className="space-y-4 text-center">
            <h1 className="text-4xl font-bold tracking-tight text-slate-900">
              {project.title}
            </h1>
            {project.description && (
              <p className="text-lg text-slate-500 max-w-2xl mx-auto">
                {project.description}
              </p>
            )}
          </div>

          <div className="space-y-6">
            {isChatsLoading ? (
              <div className="text-center py-12 text-slate-400">
                Chargement des chats...
              </div>
            ) : chats?.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-20 animate-in fade-in duration-700">
                <MessageSquare className="h-12 w-12 text-slate-100 mb-4" />
                <h3 className="text-xl font-medium text-slate-400">
                  Aucun chat pour l'instant
                </h3>
              </div>
            ) : (
              <div className="grid gap-4 max-w-2xl mx-auto">
                <h2 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2 px-1">
                  Chats récents
                </h2>
                {chats?.map((chat: ChatListResponse) => (
                  <Link
                    key={chat.id}
                    to="/projects/$projectId/chat/$chatId"
                    params={{ projectId, chatId: chat.id }}
                    className="flex items-center gap-4 p-4 rounded-2xl border border-slate-100 hover:border-primary/20 hover:bg-slate-50/50 transition-all group bg-white shadow-xs"
                  >
                    <div className="w-10 h-10 rounded-xl bg-slate-50 flex items-center justify-center text-slate-400 group-hover:bg-primary/10 group-hover:text-primary transition-colors">
                      <MessageSquare className="h-5 w-5" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <h4 className="font-semibold text-slate-800 truncate">
                        {chat.title || "Sans titre"}
                      </h4>
                      <p className="text-xs text-slate-400 font-medium">
                        {chat.message_count} messages •{" "}
                        {new Date(chat.updated_at).toLocaleDateString()}
                      </p>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </div>
        </div>
      </main>

      {/* Chat Input at Bottom */}
      <div className="absolute bottom-0 left-0 right-0 p-6 bg-linear-to-t from-white via-white/90 to-transparent">
        <div className="max-w-3xl mx-auto">
          <ChatInput
            onSendMessage={handleSendMessage}
            isStreaming={createMutation.isPending}
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
          />
        </div>
      </div>
    </div>
  );
}
