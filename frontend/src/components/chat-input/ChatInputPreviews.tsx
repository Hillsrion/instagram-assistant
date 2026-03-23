import { FileText, Loader2, X } from "lucide-react";
import type { FileAttachment } from "@/lib/types";

interface ChatInputPreviewsProps {
  attachments: FileAttachment[];
  isUploading: boolean;
  onRemove: (id: string) => void;
}

export function ChatInputPreviews({
  attachments,
  isUploading,
  onRemove,
}: ChatInputPreviewsProps) {
  if (attachments.length === 0 && !isUploading) return null;

  return (
    <div className="flex flex-wrap gap-2 p-3 pb-0">
      {attachments.map((file) => (
        <div
          key={file.id}
          className="relative w-20 h-20 rounded-xl border bg-background/80 backdrop-blur-sm overflow-hidden flex items-center justify-center shadow-md group border-muted/20 hover:border-primary/30 transition-all duration-200 hover:shadow-lg"
        >
          {file.type === "image" ? (
            <img
              src={file.url}
              alt={file.name}
              className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-110"
            />
          ) : (
            <div className="flex flex-col items-center gap-1.5 p-2 text-[10px] text-center">
              <div className="p-2 bg-muted/30 rounded-lg group-hover:bg-primary/10 transition-colors">
                <FileText className="h-6 w-6 text-muted-foreground group-hover:text-primary transition-colors" />
              </div>
              <span className="truncate w-16 font-medium text-foreground/80 group-hover:text-foreground transition-colors">
                {file.name}
              </span>
            </div>
          )}
          <button
            type="button"
            onClick={() => onRemove(file.id)}
            className="absolute top-1 right-1 h-5 w-5 rounded-full bg-destructive/90 text-white flex items-center justify-center shadow-lg opacity-0 group-hover:opacity-100 transition-all duration-200 transform scale-90 group-hover:scale-100 hover:bg-destructive"
          >
            <X className="h-3 w-3" />
          </button>
        </div>
      ))}
      {isUploading && (
        <div className="w-20 h-20 rounded-lg border bg-muted/10 flex items-center justify-center animate-pulse">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        </div>
      )}
    </div>
  );
}
