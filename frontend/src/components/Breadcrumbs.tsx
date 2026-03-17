import { useState } from "react";
import { Folder, MoreHorizontal, Settings, Trash2 } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import type { Project, Conversation } from "@/lib/types";
import { ProjectSettingsModal } from "./ProjectModals";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { deleteProject } from "@/lib/api";
import { toast } from "sonner";
import { useNavigate } from "@tanstack/react-router";

interface BreadcrumbsProps {
  project?: Project;
  conversation?: Conversation;
  showMenu?: boolean;
}

export function ProjectMenu({ project }: { project: Project }) {
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteProject(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      toast.success("Projet supprimé");
      navigate({ to: "/" });
    },
  });

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon" className="h-8 w-8 ml-1">
            <MoreHorizontal className="h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="min-w-[160px]">
          <DropdownMenuItem className="gap-2" onClick={() => setIsSettingsOpen(true)}>
            <Settings className="h-4 w-4" />
            <span>Settings</span>
          </DropdownMenuItem>
          <DropdownMenuItem 
            className="gap-2 text-destructive focus:text-destructive" 
            onClick={() => {
              if (confirm("Supprimer ce projet ?")) {
                deleteMutation.mutate(project.id);
              }
            }}
          >
            <Trash2 className="h-4 w-4" />
            <span>Supprimer</span>
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <ProjectSettingsModal
        project={project}
        open={isSettingsOpen}
        onOpenChange={setIsSettingsOpen}
      />
    </>
  );
}

export function Breadcrumbs({ project, conversation, showMenu = true }: BreadcrumbsProps) {
  if (!project) return null;

  return (
    <div className="flex items-center gap-2 text-sm text-slate-500">
      <div className="flex items-center gap-1.5 p-1 px-2 rounded-md bg-slate-100 text-slate-900 font-medium">
        <Folder className="h-4 w-4" />
        {project.title}
      </div>
      
      {conversation && (
        <>
          <span className="text-slate-300">/</span>
          <div className="flex items-center gap-2">
            <span className="text-slate-900 font-medium truncate max-w-[200px]">
              {conversation.title || "Sans titre"}
            </span>
          </div>
        </>
      )}

      {showMenu && <ProjectMenu project={project} />}
    </div>
  );
}
