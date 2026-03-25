import type { Chat, ChatListResponse } from "../types";
import { API_BASE } from "./base";

export async function getChats(): Promise<ChatListResponse[]> {
  const res = await fetch(`${API_BASE}/chats`);
  if (!res.ok) throw new Error("Failed to fetch chats");
  return res.json();
}

export async function getChat(id: string): Promise<Chat> {
  const res = await fetch(`${API_BASE}/chats/${id}`);
  if (!res.ok) throw new Error("Failed to fetch chat");
  return res.json();
}

export async function createChat(
  title?: string,
  project_id?: string,
): Promise<Chat> {
  const res = await fetch(`${API_BASE}/chats`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, project_id }),
  });
  if (!res.ok) throw new Error("Failed to create chat");
  return res.json();
}

export async function deleteChat(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/chats/${id}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error("Failed to delete chat");
}

export async function updateChat(
  id: string,
  data: {
    title?: string;
    is_favorite?: boolean;
    project_id?: string | null;
  },
): Promise<Chat> {
  const res = await fetch(`${API_BASE}/chats/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Failed to update chat");
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

export async function deleteAllChats(): Promise<void> {
  const res = await fetch(`${API_BASE}/chats`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error("Failed to delete all chats");
}

export async function exportChats(): Promise<Record<string, Chat>> {
  const res = await fetch(`${API_BASE}/chats/export`);
  if (!res.ok) throw new Error("Failed to export chats");
  return res.json();
}
