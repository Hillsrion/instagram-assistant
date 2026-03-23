import { Check } from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";

interface Agent {
  id: string;
  name: string;
  description: string;
  icon: React.ReactNode;
}

interface AgentsSectionProps {
  agents: Agent[];
  selectedAgent: string;
  onSelectAgent: (id: string) => void;
  onClose: () => void;
}

export function AgentsSection({
  agents,
  selectedAgent,
  onSelectAgent,
  onClose,
}: AgentsSectionProps) {
  return (
    <div className="flex flex-col h-full">
      <div className="p-3 border-b">
        <span className="text-sm font-medium">Choisir un agent</span>
      </div>
      <ScrollArea className="flex-1">
        <div className="p-2 space-y-0.5">
          {agents.map((agent) => (
            <button
              type="button"
              key={agent.id}
              onClick={() => {
                onSelectAgent(agent.id);
                onClose();
              }}
              className={cn(
                "flex items-center w-full px-2 py-2.5 text-sm rounded-md text-left transition-colors gap-3",
                selectedAgent === agent.id
                  ? "bg-primary/10 text-primary font-medium"
                  : "hover:bg-accent text-foreground/80",
              )}
            >
              <div className="h-9 w-9 shrink-0 rounded-lg bg-muted flex items-center justify-center text-lg border">
                {agent.icon}
              </div>
              <div className="flex flex-col min-w-0 flex-1">
                <span className="font-medium truncate">{agent.name}</span>
                <span className="text-xs text-muted-foreground truncate">
                  {agent.description}
                </span>
              </div>
              {selectedAgent === agent.id && (
                <Check className="h-4 w-4 shrink-0 text-primary" />
              )}
            </button>
          ))}
          {agents.length === 0 && (
            <div className="p-8 text-center text-sm text-muted-foreground">
              Aucun agent disponible.
            </div>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}
