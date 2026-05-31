export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "https://qasystem-production.up.railway.app";

export type DocumentItem = {
  id: string;
  title: string;
  source: string;
  created_at: string;
};

export type Citation = {
  rank: number;
  title: string;
  source: string;
  text: string;
  chunk_index: number;
};

export async function fetchDocuments(): Promise<DocumentItem[]> {
  const response = await fetch(`${API_BASE}/api/documents`, { cache: "no-store" });
  if (!response.ok) throw new Error("Could not load documents");
  return response.json();
}
