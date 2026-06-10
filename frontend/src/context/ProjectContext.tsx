import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import type { Project } from "../types";
import { fetchProjects } from "../lib/api";

type ProjectContextValue = {
  projects: Project[];
  selectedProjectId: number | null;
  selectedProject: Project | null;
  setSelectedProjectId: (projectId: number | null) => void;
  loading: boolean;
  error: string | null;
  reload: () => void;
};

export const ProjectContext = createContext<ProjectContextValue | null>(null);

export function useProjectContext(): ProjectContextValue {
  const context = useContext(ProjectContext);
  if (!context) {
    throw new Error("useProjectContext must be used inside ProjectContext provider");
  }
  return context;
}

export function ProjectProvider({ children }: { children: React.ReactNode }) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    let cancelled = false;
    async function loadProjects() {
      setLoading(true);
      setError(null);
      try {
        const projectItems = await fetchProjects();
        if (cancelled) {
          return;
        }
        setProjects(projectItems);
        if (projectItems.length === 0) {
          setSelectedProjectId(null);
          return;
        }
        setSelectedProjectId((prev) =>
          prev && projectItems.some((item) => item.id === prev) ? prev : projectItems[0].id,
        );
      } catch (loadError) {
        if (!cancelled) {
          setProjects([]);
          setSelectedProjectId(null);
          setError(loadError instanceof Error ? loadError.message : "Unknown error");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }
    void loadProjects();
    return () => {
      cancelled = true;
    };
  }, [reloadToken]);

  const selectedProject = useMemo(
    () => projects.find((item) => item.id === selectedProjectId) ?? null,
    [projects, selectedProjectId],
  );

  const contextValue = useMemo(
    () => ({
      projects,
      selectedProjectId,
      selectedProject,
      setSelectedProjectId,
      loading,
      error,
      reload: () => setReloadToken((value) => value + 1),
    }),
    [projects, selectedProjectId, selectedProject, loading, error],
  );

  return (
    <ProjectContext.Provider value={contextValue}>
      {children}
    </ProjectContext.Provider>
  );
}
