import type {
  ChatListResponse,
  ChatProject,
  ChatProjectListResponse,
} from "../types";
import { API_BASE } from "./base";

export async function getProjects(): Promise<ChatProjectListResponse[]> {
  const res = await fetch(`${API_BASE}/projects`);
  if (!res.ok) throw new Error("Failed to fetch projects");
  return res.json();
}

export async function getProject(id: string): Promise<ChatProject> {
  const res = await fetch(`${API_BASE}/projects/${id}`);
  if (!res.ok) throw new Error("Failed to fetch project");
  return res.json();
}

export async function createProject(
  data: Partial<ChatProject>,
): Promise<ChatProject> {
  const res = await fetch(`${API_BASE}/projects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Failed to create project");
  return res.json();
}

export async function updateProject(
  id: string,
  data: Partial<ChatProject>,
): Promise<ChatProject> {
  const res = await fetch(`${API_BASE}/projects/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Failed to update project");
  return res.json();
}

export async function deleteProject(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/projects/${id}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error("Failed to delete project");
}

export async function getProjectChats(
  projectId: string,
): Promise<ChatListResponse[]> {
  const res = await fetch(`${API_BASE}/projects/${projectId}/chats`);
  if (!res.ok) throw new Error("Failed to fetch project chats");
  return res.json();
}

export async function bulkUpdateProjectChats(
  projectId: string,
  chatIds: string[],
  action: "add" | "remove" | "set",
): Promise<{ status: string; updated_count: number }> {
  const res = await fetch(`${API_BASE}/projects/${projectId}/chats/bulk`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_ids: chatIds, action }),
  });
  if (!res.ok) throw new Error("Failed to bulk update chats");
  return res.json();
}
