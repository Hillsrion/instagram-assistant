import { ChevronDown, Gauge, Lightbulb } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";

export type ChatMode = "fast" | "reflexion";

interface ModeSelectorProps {
  mode: ChatMode;
  onModeChange: (mode: ChatMode) => void;
  className?: string;
}

const MODES = [
  {
    id: "fast" as ChatMode,
    label: "Rapide",
    description: "Réponses rapides",
    icon: Gauge,
  },
  {
    id: "reflexion" as ChatMode,
    label: "Réflexion",
    description: "Raisonnement approfondi",
    icon: Lightbulb,
  },
];

export function ModeSelector({
  mode,
  onModeChange,
  className,
}: ModeSelectorProps) {
  const currentMode = MODES.find((m) => m.id === mode) || MODES[0];

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className={cn(
            "h-7 gap-1.5 px-2 text-xs font-medium transition-all duration-300 rounded-lg focus-visible:ring-0",
            className,
          )}
        >
          <currentMode.icon className="h-3.5 w-3.5" />
          <span>{currentMode.label}</span>
          <ChevronDown className="h-3 w-3 opacity-50" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="end"
        className="w-64 p-1 rounded-xl shadow-lg border-muted/50"
      >
        {MODES.map((m) => (
          <DropdownMenuItem
            key={m.id}
            onClick={() => onModeChange(m.id)}
            className={cn(
              "flex flex-col items-start gap-0.5 p-3 cursor-pointer rounded-lg transition-colors",
              mode === m.id ? "bg-muted/50" : "hover:bg-muted/30",
            )}
          >
            <div className="flex items-center gap-2 w-full">
              <m.icon
                className={cn(
                  "h-4 w-4",
                  mode === m.id ? "text-primary" : "text-muted-foreground",
                )}
              />
              <span
                className={cn(
                  "font-semibold text-sm",
                  mode === m.id ? "text-foreground" : "text-muted-foreground",
                )}
              >
                {m.label}
              </span>
            </div>
            <span className="text-[11px] text-muted-foreground ml-6">
              {m.description}
            </span>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
