import { authenticatedFetch } from "./auth";

export type FileEntry = { path: string; name: string; size_bytes: number; modified_at: string; source: string };
export type ProjectView = { id: string; name: string; path: string; project_type: string; modified_at: string | null; repository_id: string | null };
export type GitRepositoryView = { id: string; name: string; path: string; branch: string | null; commit: string | null; subject: string | null; modified_at: string | null; clean: boolean | null; ahead: number | null; behind: number | null; available: boolean; reason: string | null };
export type DockerContainerView = { id: string; name: string; image: string; state: "running" | "exited" | "created" | "paused" | "restarting" | "removing" | "dead" | "unknown"; health: string | null; created_at: string | null; ports: string[]; restart_policy: string | null; compose_service: string | null };

type ViewResponse<T> = { items: T[]; available: boolean; reason: string | null; next_cursor?: string | null };

async function read<T>(path: string): Promise<ViewResponse<T>> {
  const response = await authenticatedFetch(path, { cache: "no-store" });
  if (!response.ok) throw new Error(`Workspace view request failed with ${response.status}`);
  return response.json() as Promise<ViewResponse<T>>;
}

export function listRecentFiles(limit = 50) { return read<FileEntry>(`/api/v1/files/recent?limit=${limit}`); }
export function listProjects() { return read<ProjectView>("/api/v1/projects"); }
export function listGitRepositories() { return read<GitRepositoryView>("/api/v1/git/repositories"); }
export function listDockerContainers() { return read<DockerContainerView>("/api/v1/docker/containers"); }
