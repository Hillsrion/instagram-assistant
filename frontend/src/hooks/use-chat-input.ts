import { useRef, useState } from "react";
import type { DateRange } from "react-day-picker";
import type { ChatMode } from "@/components/ModeSelector";
import type { FileAttachment } from "@/lib/types";

interface UseChatInputProps {
  onSendMessage: (
    content: string,
    options: {
      participant?: string;
      group?: string;
      broadSearch?: boolean;
      model?: string;
      mode?: string;
      date?: DateRange;
      attachments?: FileAttachment[];
    },
  ) => void;
  filterParticipant: string;
  filterGroup: string;
  filterBroad: boolean;
  selectedModel: string;
  selectedMode: ChatMode;
  filterDate?: DateRange;
}

export function useChatInput({
  onSendMessage,
  filterParticipant,
  filterGroup,
  filterBroad,
  selectedModel,
  selectedMode,
  filterDate,
}: UseChatInputProps) {
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

      const newAttachments: FileAttachment[] = await response.json();
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

  return {
    inputRef,
    attachments,
    isUploading,
    handleSubmit,
    handleFilesSelected,
    removeAttachment,
  };
}
