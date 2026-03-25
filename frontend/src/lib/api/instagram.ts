import type { InstagramConversation, SourceGroup } from "../types";
import { API_BASE } from "./base";

export interface SourceGroupUpdate {
  title: string;
}

export interface SourceGroupBulkUpdate {
  thread_ids: string[];
  action: "add" | "remove";
}

export const instagramApi = {
  /**
   * List all unique Instagram threads from the summary index.
   */
  listThreads: async (): Promise<InstagramConversation[]> => {
    const res = await fetch(`${API_BASE}/instagram/threads`);
    if (!res.ok) throw new Error("Failed to fetch threads");
    return res.json();
  },

  /**
   * List all user-defined Instagram source groups.
   */
  listGroups: async (): Promise<SourceGroup[]> => {
    const res = await fetch(`${API_BASE}/instagram/groups`);
    if (!res.ok) throw new Error("Failed to fetch groups");
    return res.json();
  },

  /**
   * Create a new source group.
   */
  createGroup: async (data: SourceGroupUpdate): Promise<SourceGroup> => {
    const res = await fetch(`${API_BASE}/instagram/groups`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error("Failed to create group");
    return res.json();
  },

  /**
   * Delete a source group.
   */
  deleteGroup: async (groupId: string): Promise<void> => {
    const res = await fetch(`${API_BASE}/instagram/groups/${groupId}`, {
      method: "DELETE",
    });
    if (!res.ok) throw new Error("Failed to delete group");
  },

  /**
   * Bulk update threads in a source group.
   */
  bulkUpdateGroupThreads: async (
    groupId: string,
    data: SourceGroupBulkUpdate,
  ): Promise<{ updated_count: number }> => {
    const res = await fetch(`${API_BASE}/instagram/groups/${groupId}/bulk`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error("Failed to bulk update threads");
    return res.json();
  },
};
