import { fetchEventSource } from "@microsoft/fetch-event-source";
import type { FileAttachment } from "../types";
import { API_BASE } from "./base";

export interface ChatStreamOptions {
  message: string;
  chat_id: string;
  model?: string;
  mode?: string;
  agent_id?: string;
  participant_filter?: string;
  use_about_person?: boolean;
  group_filter?: string;
  date_filter?: any;
  attachments?: FileAttachment[];
  signal?: AbortSignal;
  onMessage: (data: any) => void;
  onError: (err: any) => void;
}

export async function streamChat(options: ChatStreamOptions) {
  const { onMessage, onError, signal, ...body } = options;

  await fetchEventSource(`${API_BASE}/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
    signal,
    async onmessage(ev) {
      if (ev.data) {
        try {
          const data = JSON.parse(ev.data);
          onMessage(data);
        } catch (e) {
          console.error("Failed to parse event data", e);
        }
      }
    },
    onerror(err) {
      onError(err);
    },
  });
}
