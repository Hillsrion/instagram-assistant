import { ChevronDown, X } from "lucide-react";

interface Agent {
  name: string;
}

interface ChatInputAgentPillProps {
  currentAgent: Agent;
  onDeactivate: () => void;
}

export function ChatInputAgentPill({
  currentAgent,
  onDeactivate,
}: ChatInputAgentPillProps) {
  return (
    <div className="bg-primary text-primary-foreground px-3 py-1.5 flex items-center justify-between text-xs font-semibold animate-in slide-in-from-top-2 duration-300">
      <div className="flex items-center gap-2">
        <span className="flex items-center gap-1 opacity-90">
          @{currentAgent.name}
          <ChevronDown className="h-3 w-3 ml-0.5" />
        </span>
      </div>
      <button
        type="button"
        onClick={onDeactivate}
        className="p-1 hover:bg-white/20 rounded-full transition-colors"
        title="Désactiver l'agent"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}
