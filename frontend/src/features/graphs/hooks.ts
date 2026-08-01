import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "./api";

export function useGraphs() {
  return useQuery({
    queryKey: ["graphs"],
    queryFn: api.listGraphs,
  });
}

export function useGraph(graphId: string) {
  return useQuery({
    queryKey: ["graphs", graphId],
    queryFn: () => api.getGraph(graphId),
    enabled: Boolean(graphId),
  });
}

export function useCreateGraph() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.createGraph,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["graphs"] }),
  });
}

export function useUpdateGraph() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ graphId, ...payload }: { graphId: string; title?: string; description?: string }) =>
      api.updateGraph(graphId, payload),
    onSuccess: (graph) => {
      qc.invalidateQueries({ queryKey: ["graphs"] });
      qc.setQueryData(["graphs", graph.id], graph);
    },
  });
}

export function useDeleteGraph() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.deleteGraph,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["graphs"] }),
  });
}
