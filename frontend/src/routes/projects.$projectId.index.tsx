import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { MessageSquare } from "lucide-react";
import { Breadcrumbs, ProjectMenu } from "@/components/Breadcrumbs";
import { ChatInput } from "@/components/ChatInput";
import { useChatFilters } from "@/hooks/use-chat-filters";
import {
  createConversation,
  getProject,
  getProjectConversations,
} from "@/lib/api";

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

  const { data: conversations, isLoading: isConvsLoading } = useQuery({
    queryKey: ["project-conversations", projectId],
    queryFn: () => getProjectConversations(projectId),
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
  } = useChatFilters();

  const createMutation = useMutation({
    mutationFn: (title?: string) => createConversation(title, projectId),
  });

  const handleSendMessage = async (content: string, options: any) => {
    try {
      const newConv = await createMutation.mutateAsync(
        content.slice(0, 30) + (content.length > 30 ? "..." : ""),
      );

      navigate({
        to: "/projects/$projectId/chat/$chatId",
        params: { projectId, chatId: newConv.id },
        search: {
          q: content,
          p: options.participant || undefined,
          g: options.group || undefined,
          b: options.broadSearch || undefined,
        },
      });

      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ["conversations"] });
        queryClient.invalidateQueries({
          queryKey: ["project-conversations", projectId],
        });
      }, 500);
    } catch (error) {
      console.error("Failed to create conversation:", error);
    }
  };

  if (isProjectLoading)
    return <div className="p-8 text-center">Chargement du projet...</div>;
  if (!project)
    return (
      <div className="p-8 text-center text-destructive">Projet non trouvé</div>
    );

  return (
    <div className="flex flex-col h-full bg-white relative">
      <header className="flex items-center justify-between px-6 py-4 border-b">
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
            {isConvsLoading ? (
              <div className="text-center py-12">
                Chargement des conversations...
              </div>
            ) : conversations?.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-20 animate-in fade-in duration-700">
                <MessageSquare className="h-12 w-12 text-slate-200 mb-4" />
                <h3 className="text-xl font-medium text-slate-400">
                  Aucune conversation pour l'instant
                </h3>
              </div>
            ) : (
              <div className="grid gap-4 max-w-2xl mx-auto">
                <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-2">
                  Conversations récentes
                </h2>
                {conversations?.map((conv) => (
                  <Link
                    key={conv.id}
                    to="/projects/$projectId/chat/$chatId"
                    params={{ projectId, chatId: conv.id }}
                    className="flex items-center gap-4 p-4 rounded-2xl border border-slate-100 hover:border-primary/20 hover:bg-slate-50/50 transition-all group"
                  >
                    <div className="w-10 h-10 rounded-xl bg-slate-50 flex items-center justify-center text-slate-400 group-hover:bg-primary/10 group-hover:text-primary transition-colors">
                      <MessageSquare className="h-5 w-5" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <h4 className="font-medium text-slate-900 truncate">
                        {conv.title || "Sans titre"}
                      </h4>
                      <p className="text-xs text-slate-400">
                        {conv.message_count} messages •{" "}
                        {new Date(conv.updated_at).toLocaleDateString()}
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
            isLoading={createMutation.isPending}
            autoFocus
          />
        </div>
      </div>
    </div>
  );
}
