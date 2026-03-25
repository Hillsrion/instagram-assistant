import { Brain, Check, Search } from "lucide-react";
import type { AgentStep } from "@/lib/types";
import { cn } from "@/lib/utils";

interface AgentProgressionProps {
  steps: AgentStep[];
  isStreaming?: boolean;
}

export function AgentProgression({
  steps,
  isStreaming,
}: AgentProgressionProps) {
  if (!steps || steps.length === 0) return null;

  return (
    <div className="flex flex-col gap-2 my-2 py-2 border-l-2 border-primary/10 pl-4 animate-in fade-in slide-in-from-left-2 duration-500">
      <div className="flex items-center gap-2 text-xs font-semibold text-primary/60 uppercase tracking-wider mb-1">
        <Brain className="h-3.5 w-3.5" />
        <span>Raisonnement de l'agent</span>
      </div>

      <div className="space-y-3">
        {steps.map((step, idx) => (
          <div
            key={`${step.step}-${step.agent_type}-${idx}`}
            className="group flex items-start gap-3 animate-in fade-in slide-in-from-top-1 duration-300"
            style={{ animationDelay: `${idx * 50}ms` }}
          >
            <div
              className={cn(
                "mt-0.5 rounded-full p-1 shrink-0",
                step.agent_type === "thought"
                  ? "bg-blue-50 text-blue-500"
                  : step.agent_type === "action"
                    ? "bg-amber-50 text-amber-500"
                    : "bg-green-50 text-green-500",
              )}
            >
              {step.agent_type === "thought" && <Brain className="h-3 w-3" />}
              {step.agent_type === "action" && <Search className="h-3 w-3" />}
              {step.agent_type === "observation" && (
                <Check className="h-3 w-3" />
              )}
            </div>

            <div className="flex flex-col gap-0.5">
              <span
                className={cn(
                  "text-[13px] leading-tight transition-colors",
                  idx === steps.length - 1 && isStreaming
                    ? "text-foreground font-medium"
                    : "text-muted-foreground",
                )}
              >
                {step.label}
              </span>
              {step.tool && (
                <span className="text-[10px] font-mono text-muted-foreground/50">
                  {step.tool}
                </span>
              )}
            </div>
          </div>
        ))}

        {isStreaming && (
          <div className="flex items-center gap-2 px-1 py-0.5">
            <span className="flex h-1.5 w-1.5 rounded-full bg-primary/40 animate-pulse" />
            <span className="text-[11px] text-muted-foreground/60 italic">
              Réflexion continue...
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
