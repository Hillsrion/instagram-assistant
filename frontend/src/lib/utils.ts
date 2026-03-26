import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Filters out the user's own username(s) and generic placeholders from a list of participants.
 * @param participants List of participant names from Instagram export.
 * @param ownUsername Comma-separated list of the user's own usernames.
 * @returns Filtered list of participant names.
 */
export function filterParticipants(
  participants: string[] | undefined | null,
  ownUsername: string,
): string[] {
  if (!participants) return [];

  const ownNames = ownUsername
    .split(",")
    .map((name) => name.trim().toLowerCase())
    .filter((name) => name.length > 0);

  return participants.filter((p) => {
    const lowerP = p.trim().toLowerCase();
    if (lowerP === "me" || lowerP === "user") return false;
    if (ownNames.includes(lowerP)) return false;
    return true;
  });
}
