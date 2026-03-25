import type { Conversation, ConversationListResponse } from "../types";
import { API_BASE } from "./base";

export async function getConversations(): Promise<ConversationListResponse[]> {
  const res = await fetch(`${API_BASE}/conversations`);
  if (!res.ok) throw new Error("Failed to fetch conversations");
  return res.json();
}

export async function getConversation(id: string): Promise<Conversation> {
  const res = await fetch(`${API_BASE}/conversations/${id}`);
  if (!res.ok) throw new Error("Failed to fetch conversation");
  return res.json();
}

export async function createConversation(
  title?: string,
  project_id?: string,
): Promise<Conversation> {
  const res = await fetch(`${API_BASE}/conversations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, project_id }),
  });
  if (!res.ok) throw new Error("Failed to create conversation");
  return res.json();
}

export async function deleteConversation(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/conversations/${id}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error("Failed to delete conversation");
}

export async function updateConversation(
  id: string,
  data: {
    title?: string;
    is_favorite?: boolean;
    project_id?: string | null;
  },
): Promise<Conversation> {
  const res = await fetch(`${API_BASE}/conversations/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Failed to update conversation");
  return res.json();
}

export async function evaluateTitle(
  message: string,
  model?: string,
): Promise<{ title: string }> {
  const res = await fetch(`${API_BASE}/evaluate-title`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, model }),
  });
  if (!res.ok) throw new Error("Failed to evaluate title");
  return res.json();
}

export async function deleteAllConversations(): Promise<void> {
  const res = await fetch(`${API_BASE}/conversations`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error("Failed to delete all conversations");
}

export async function exportConversations(): Promise<
  Record<string, Conversation>
> {
  const res = await fetch(`${API_BASE}/conversations/export`);
  if (!res.ok) throw new Error("Failed to export conversations");
  return res.json();
}
