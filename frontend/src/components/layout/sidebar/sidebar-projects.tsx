import { Link, useMatchRoute } from "@tanstack/react-router";
import { ChevronDown, ChevronRight } from "lucide-react";
import type {
  ConversationListResponse,
  ProjectListResponse,
} from "@/lib/types";
import { cn } from "@/lib/utils";

interface SidebarProjectsProps {
  projects: ProjectListResponse[] | undefined;
  conversations: ConversationListResponse[] | undefined;
  expandedProjects: Record<string, boolean>;
  toggleProject: (projectId: string) => void;
}

export function SidebarProjects({
  projects,
  conversations,
  expandedProjects,
  toggleProject,
}: SidebarProjectsProps) {
  const matchRoute = useMatchRoute();

  if (!projects || projects.length === 0) return null;

  return (
    <>
      <div className="px-2 py-2 text-xs font-medium text-muted-foreground shrink-0 mt-4">
        Projets
      </div>
      <div className="space-y-1 mb-4">
        {projects.map((project) => (
          <div key={project.id} className="space-y-0.5">
            <div
              role="button"
              tabIndex={0}
              className={cn(
                "group flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-muted/50 cursor-pointer transition-colors outline-none focus-visible:ring-2 focus-visible:ring-primary",
                matchRoute({
                  to: "/projects/$projectId" as any,
                  params: { projectId: project.id } as any,
                }) && "bg-muted",
              )}
              onClick={() => toggleProject(project.id)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  toggleProject(project.id);
                }
              }}
            >
              <div className="opacity-0 group-hover:opacity-100 transition-opacity">
                {expandedProjects[project.id] ? (
                  <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
                ) : (
                  <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
                )}
              </div>
              <Link
                to={"/projects/$projectId" as any}
                params={{ projectId: project.id } as any}
                className="flex-1 text-sm font-medium truncate"
                onClick={(e) => e.stopPropagation()}
              >
                {project.title}
              </Link>
            </div>

            {expandedProjects[project.id] && (
              <div className="ml-4 pl-2 border-l border-muted-foreground/20 space-y-0.5">
                {conversations
                  ?.filter((c) => c.project_id === project.id)
                  .map((conv) => (
                    <Link
                      key={conv.id}
                      to="/chat/$chatId"
                      params={{ chatId: conv.id }}
                      className={cn(
                        "block px-2 py-1 text-xs text-muted-foreground hover:text-foreground hover:bg-muted/30 rounded-md truncate transition-colors",
                        matchRoute({
                          to: "/chat/$chatId",
                          params: { chatId: conv.id },
                        }) && "bg-muted text-foreground",
                      )}
                    >
                      {conv.title || "Nouvelle conversation"}
                    </Link>
                  ))}
                {conversations?.filter((c) => c.project_id === project.id)
                  .length === 0 && (
                  <div className="px-2 py-1 text-[10px] text-muted-foreground italic">
                    Aucune conversation
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </>
  );
}
