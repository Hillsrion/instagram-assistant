import { cn } from "@/lib/utils";

interface TypingIndicatorProps {
  className?: string;
}

export function TypingIndicator({ className }: TypingIndicatorProps) {
  // Snake pattern order: 1->2->3->6->9->8->7->4->5
  // Corresponds to grid indices: 0, 1, 2, 5, 8, 7, 6, 3, 4
  const delayClasses = [
    "[animation-delay:0s]",
    "[animation-delay:0.15s]",
    "[animation-delay:0.3s]",
    "[animation-delay:1.05s]",
    "[animation-delay:1.2s]",
    "[animation-delay:0.45s]",
    "[animation-delay:0.9s]",
    "[animation-delay:0.75s]",
    "[animation-delay:0.6s]",
  ];

  return (
    <div className={cn("grid grid-cols-3 gap-[3px] w-fit", className)}>
      {[...Array(9)].map((_, i) => (
        <div
          key={i}
          className={cn(
            "w-1 h-1 rounded-full bg-current opacity-20 scale-[0.85] text-primary animate-[snake-illuminate_1.5s_infinite_ease-in-out]",
            delayClasses[i],
          )}
        />
      ))}
    </div>
  );
}
