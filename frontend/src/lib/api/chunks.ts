import type { ChunkDetail } from "../types";
import { API_BASE } from "./base";

export async function getChunkContent(chunkId: string): Promise<ChunkDetail> {
  const res = await fetch(`${API_BASE}/chunks/${chunkId}`);
  if (!res.ok) throw new Error("Failed to fetch chunk content");
  return res.json();
}
