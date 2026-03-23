import { format } from "date-fns";
import { fr } from "date-fns/locale";
import {
  CalendarDays,
  FileText,
  Instagram,
  Loader2,
  Plus,
  Send,
  Sparkles,
  StopCircle,
  Users,
  X,
} from "lucide-react";
import { useRef, useState } from "react";
import type { DateRange } from "react-day-picker";
import { ChatInputMenu } from "@/components/ChatInputMenu";
import { type ChatMode, ModeSelector } from "@/components/ModeSelector";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { FileAttachment } from "@/lib/types";
import { cn } from "@/lib/utils";

interface ChatInputProps {
  onSendMessage: (
    content: string,
    options: {
      participant?: string;
      group?: string;
      broadSearch?: boolean;
      model?: string;
      mode?: string;
      agent_id?: string;
      date?: DateRange;
      attachments?: FileAttachment[];
    },
  ) => void;
  isStreaming: boolean;
  stopStream: () => void;

  selectedModel: string;
  setSelectedModel: (model: string) => void;
  selectedMode: ChatMode;
  setSelectedMode: (mode: ChatMode) => void;
  developerMode: boolean;
  modelsData?: {
    models: Array<{ name: string }>;
    default_model: string;
  };
  filterParticipant: string;
  setFilterParticipant: (p: string) => void;
  filterGroup: string;
  setFilterGroup: (g: string) => void;
  filterBroad: boolean;
  setFilterBroad: (b: boolean) => void;
  filterDate?: DateRange;
  setFilterDate: (date: DateRange | undefined) => void;
  participantNames: string[];
  selectedAgent: string;
  setSelectedAgent: (id: string) => void;
  className?: string;
  isLoading?: boolean;
  autoFocus?: boolean;
  isHome?: boolean;
}

export function ChatInput({
  onSendMessage,
  isStreaming,
  stopStream,

  selectedModel,
  setSelectedModel,
  selectedMode,
  setSelectedMode,
  developerMode,
  modelsData,
  filterParticipant,
  setFilterParticipant,
  filterGroup,
  setFilterGroup,
  filterBroad,
  setFilterBroad,
  filterDate,
  setFilterDate,
  participantNames,
  selectedAgent,
  setSelectedAgent,
  className,
  isLoading,
  autoFocus = false,
  isHome = false,
}: ChatInputProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [attachments, setAttachments] = useState<FileAttachment[]>([]);
  const [isUploading, setIsUploading] = useState(false);

  const handleSubmit = (e?: React.FormEvent) => {
    e?.preventDefault();
    if (inputRef.current?.value || attachments.length > 0) {
      onSendMessage(inputRef.current?.value || "", {
        participant: filterParticipant,
        group: filterGroup,
        broadSearch: filterBroad,
        model: selectedModel,
        mode: selectedMode,
        date: filterDate,
        attachments: attachments,
      });
      if (inputRef.current) inputRef.current.value = "";
      setAttachments([]);
    }
  };

  const handleFilesSelected = async (files: FileList) => {
    if (attachments.length + files.length > 5) {
      alert("Maximum 5 fichiers autorisés");
      return;
    }

    setIsUploading(true);
    const formData = new FormData();
    for (let i = 0; i < files.length; i++) {
      formData.append("files", files[i]);
    }

    try {
      const response = await fetch("/api/upload", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) throw new Error("Erreur lors de l'envoi");

      const newAttachments: FileAttachment[] = (await response.ok)
        ? await response.json()
        : [];
      setAttachments((prev) => [...prev, ...newAttachments]);
    } catch (error) {
      console.error("Upload error:", error);
      alert("Erreur lors du téléchargement des fichiers");
    } finally {
      setIsUploading(false);
    }
  };

  const removeAttachment = (id: string) => {
    setAttachments((prev) => prev.filter((a) => a.id !== id));
  };

  const selectedCount = (filterParticipant ? 1 : 0) + (filterGroup ? 1 : 0);

  return (
    <div
      className={cn(
        "w-full transition-all duration-700 ease-in-out",
        isHome
          ? "fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-50 p-4 max-w-2xl animate-in fade-in zoom-in-95 duration-700"
          : "relative p-0",
        className,
      )}
      style={{
        viewTransitionName: "chat-input",
      }}
    >
      {isHome && (
        <div className="flex flex-col items-center gap-12 mb-10 text-center animate-in fade-in slide-in-from-bottom-8 duration-1000 ease-out">
          <div className="h-16 w-16 rounded-2xl bg-primary/10 flex items-center justify-center border border-primary/20 shadow-sm">
            <Instagram className="h-10 w-10 text-primary" />
          </div>
        </div>
      )}
      <div className="bg-card border rounded-2xl shadow-xl overflow-hidden focus-within:ring-1 focus-within:ring-primary/20 focus-within:border-primary/30 transition-all duration-300">
        {/* Previews Area */}
        {(attachments.length > 0 || isUploading) && (
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
                {/* Remove button with improved look */}
                <button
                  type="button"
                  onClick={() => removeAttachment(file.id)}
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
        )}
        {/* Unified Container Input Area */}
        <div className="flex gap-2 relative p-2 px-3">
          <Input
            ref={inputRef}
            autoFocus={autoFocus}
            placeholder={
              filterParticipant
                ? `Demander quelque chose sur ${filterParticipant}...`
                : filterGroup
                  ? `Demander quelque chose sur le groupe ${filterGroup}...`
                  : "Quels ont été les moments forts de mes conversations avec Marie ?"
            }
            className="flex-1 border-0 shadow-none focus-visible:ring-0 text-base min-h-[44px] bg-transparent"
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSubmit();
              }
            }}
            disabled={isStreaming}
          />

          <div className="flex items-center">
            {isStreaming ? (
              <Button
                variant="destructive"
                size="icon"
                onClick={stopStream}
                className="h-8 w-8 rounded-full"
              >
                <StopCircle className="h-4 w-4" />
              </Button>
            ) : (
              <Button
                size="icon"
                onClick={() => handleSubmit()}
                disabled={isLoading}
                className="h-8 w-8 rounded-full"
              >
                <Send className="h-4 w-4" />
              </Button>
            )}
          </div>
        </div>

        {/* Toolbar: Inside the rounded container */}
        <div className="flex items-center justify-between px-3 pb-2 border-t border-muted/30 pt-2 bg-muted/5">
          <div className="flex items-center gap-1.5">
            {/* 1. CHAT INPUT MENU */}
            <ChatInputMenu
              participantNames={participantNames}
              selectedParticipant={filterParticipant}
              onSelectParticipant={(p) => {
                setFilterParticipant(p);
                if (p) setFilterGroup("");
                if (!p) setFilterBroad(false);
              }}
              isBroadSearch={filterBroad}
              onBroadSearchChange={setFilterBroad}
              selectedGroup={filterGroup}
              onSelectGroup={(g) => {
                setFilterGroup(g);
                if (g) {
                  setFilterParticipant("");
                  setFilterBroad(false);
                }
              }}
              filterDate={filterDate}
              setFilterDate={setFilterDate}
              onReset={() => {
                setFilterParticipant("");
                setFilterGroup("");
                setFilterBroad(false);
                setFilterDate(undefined);
              }}
              onFilesSelected={handleFilesSelected}
              selectedAgent={selectedAgent}
              onSelectAgent={setSelectedAgent}
            >
              <Button
                variant="outline"
                size="sm"
                className={cn(
                  "gap-1.5 h-7 w-7 p-0 rounded-lg text-muted-foreground hover:text-foreground transition-colors",
                  selectedCount > 0 || filterDate?.from
                    ? "border-primary/50 text-primary hover:text-primary hover:bg-primary/10"
                    : "border-dashed hover:border-solid",
                )}
              >
                <Plus className="h-4 w-4" />
              </Button>
            </ChatInputMenu>

            {/* Selected Filters Badges */}
            {selectedCount > 0 && (
              <Badge
                variant="secondary"
                className="h-6 px-2 text-[10px] font-medium bg-primary/10 text-primary hover:bg-primary/20 cursor-default"
              >
                <Users className="h-3 w-3 mr-1" />
                {selectedCount} compte{selectedCount > 1 ? "s" : ""}
              </Badge>
            )}

            {filterDate?.from && (
              <Badge
                variant="secondary"
                className="h-6 px-2 text-[10px] font-medium bg-primary/10 text-primary hover:bg-primary/20 cursor-default"
              >
                <CalendarDays className="h-3 w-3 mr-1" />
                {filterDate.to
                  ? `${format(filterDate.from, "d MMM", { locale: fr })} - ${format(filterDate.to, "d MMM yy", { locale: fr })}`
                  : format(filterDate.from, "d MMM yyyy", { locale: fr })}
              </Badge>
            )}

            {/* 3. MODE OR MODEL SELECTOR */}
            {developerMode ? (
              // Developer Mode: Show Model Selector
              modelsData?.models &&
              modelsData.models.length > 0 && (
                <Select
                  value={selectedModel || modelsData.default_model || ""}
                  onValueChange={setSelectedModel}
                >
                  <SelectTrigger className="h-7 w-auto gap-1.5 text-xs font-medium border-0 bg-transparent hover:bg-muted focus:ring-0 px-2 transition-all duration-300 rounded-lg focus-visible:ring-0">
                    <Sparkles className="h-3 w-3" />
                    <SelectValue placeholder="Modèle" />
                  </SelectTrigger>
                  <SelectContent>
                    {modelsData.models.map((model) => (
                      <SelectItem
                        key={model.name}
                        value={model.name}
                        className="text-xs"
                      >
                        {model.name.includes(":")
                          ? model.name
                          : `${model.name}:latest`}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )
            ) : (
              // Regular Mode: Show Mode Selector
              <ModeSelector
                mode={selectedMode}
                onModeChange={setSelectedMode}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
