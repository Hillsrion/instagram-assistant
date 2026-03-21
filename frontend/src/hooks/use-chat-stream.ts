import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useRef, useState } from "react";
import type { DateRange } from "react-day-picker";
import { toast } from "sonner";
import { evaluateTitle, streamChat, updateConversation } from "@/lib/api";
import type { Message } from "@/lib/types";

interface UseChatStreamProps {
  chatId: string;
  onFinish?: () => void;
}

export function useChatStream({ chatId, onFinish }: UseChatStreamProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamStatus, setStreamStatus] = useState<string>("");
  const queryClient = useQueryClient();
  const abortController = useRef<AbortController | null>(null);

  const sendMessage = useCallback(
    async (
      content: string,
      filters?: {
        participant?: string;
        group?: string;
        broadSearch?: boolean;
        model?: string;
        mode?: string;
        date?: DateRange;
      },
    ) => {
      if (!content.trim()) return;

      // Add user message
      const userMsg: Message = {
        role: "user",
        content,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, userMsg]);
      setIsStreaming(true);
      setStreamStatus("Initializing...");

      // Prepare assistant message placeholder
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "",
          timestamp: new Date().toISOString(),
        },
      ]);

      abortController.current = new AbortController();

      try {
        await streamChat({
          message: content,
          conversation_id: chatId,
          model: filters?.model || undefined,
          mode: filters?.mode || "fast",
          participant_filter: filters?.participant || undefined,
          use_about_person: filters?.broadSearch || false,
          group_filter: filters?.group || undefined,
          date_filter: filters?.date || undefined,
          signal: abortController.current.signal || undefined,
          onMessage: (data) => {
            if (data.type === "progress") {
              setStreamStatus(data.message);
            } else if (data.type === "chunk") {
              setMessages((prev) => {
                const last = prev[prev.length - 1];
                if (last.role === "assistant") {
                  return [
                    ...prev.slice(0, -1),
                    { ...last, content: last.content + data.content },
                  ];
                }
                return prev;
              });
            } else if (data.type === "sources") {
              setMessages((prev) => {
                const last = prev[prev.length - 1];
                if (last.role === "assistant") {
                  return [
                    ...prev.slice(0, -1),
                    {
                      ...last,
                      sources: data.sources,
                      summary_sources: data.summary_sources || [],
                    },
                  ];
                }
                return prev;
              });
            } else if (data.type === "followups") {
              setMessages((prev) => {
                const last = prev[prev.length - 1];
                if (last.role === "assistant") {
                  return [
                    ...prev.slice(0, -1),
                    { ...last, followups: data.questions },
                  ];
                }
                return prev;
              });
            } else if (data.type === "done") {
              setIsStreaming(false);
              setStreamStatus("");

              // Auto-evaluate title if it's the first message
              if (messages.length === 0) {
                evaluateTitle(content, filters?.model || undefined)
                  .then(({ title }) => updateConversation(chatId, { title }))
                  .catch((err) =>
                    console.error("Failed to auto-update title:", err),
                  );
              }

              queryClient.invalidateQueries({ queryKey: ["conversations"] });
              queryClient.invalidateQueries({
                queryKey: ["conversation", chatId],
              });
              if (onFinish) onFinish();
            } else if (data.error) {
              throw new Error(data.error);
            }
          },
          onError: (err) => {
            console.error("Stream error:", err);
            toast.error("Failed to send message");
            setIsStreaming(false);
            setStreamStatus("");
          },
        });
      } catch (error) {
        console.error("Fetch error:", error);
        setIsStreaming(false);
      }
    },
    [chatId, queryClient, onFinish, messages],
  );

  const stopStream = useCallback(() => {
    if (abortController.current) {
      abortController.current.abort();
      abortController.current = null;
      setIsStreaming(false);
      setStreamStatus("Stopped");
    }
  }, []);

  return {
    messages,
    setMessages,
    sendMessage,
    isStreaming,
    streamStatus,
    stopStream,
  };
}
