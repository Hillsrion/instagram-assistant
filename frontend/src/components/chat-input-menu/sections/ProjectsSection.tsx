import { BookOpen, Plus, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { Project } from "@/lib/types";

interface ProjectsSectionProps {
  projectSearch: string;
  setProjectSearch: (s: string) => void;
  filteredProjects: Project[];
}

export function ProjectsSection({
  projectSearch,
  setProjectSearch,
  filteredProjects,
}: ProjectsSectionProps) {
  return (
    <div className="flex flex-col h-full">
      <div className="p-3 border-b flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium">Rechercher</span>
          <Button variant="ghost" size="sm" className="h-7 text-xs gap-1">
            <Plus className="h-3 w-3" />
            Nouveau Projet
          </Button>
        </div>
        <div className="relative">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Rechercher des projets..."
            className="pl-9 h-9 border-none bg-muted/50 focus-visible:ring-0 text-sm rounded-sm"
            value={projectSearch}
            onChange={(e) => setProjectSearch(e.target.value)}
          />
        </div>
      </div>
      <ScrollArea className="flex-1">
        <div className="p-2 space-y-2">
          {filteredProjects.map((proj) => (
            <div
              key={proj.id}
              className="flex items-center gap-3 p-2 rounded-md hover:bg-accent transition-colors cursor-pointer border border-transparent hover:border-border"
            >
              <div className="h-10 w-10 shrink-0 rounded-md bg-muted flex items-center justify-center border">
                <BookOpen className="h-5 w-5 text-orange-500" />
              </div>
              <div className="flex flex-col min-w-0 flex-1">
                <span className="text-sm font-medium text-foreground truncate">
                  {proj.title}
                </span>
                <span className="text-xs text-muted-foreground">Projet</span>
              </div>
            </div>
          ))}
          {filteredProjects.length === 0 && (
            <div className="p-8 text-center text-sm text-muted-foreground">
              Aucun projet trouvé.
            </div>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}
