import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { AppDialog } from "../shared/ui/AppDialog";
import { AIConnectionTester } from "../shared/ui/AIConnectionTester";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

export function AppProviders({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      {children}
      <AppDialog />
      <AIConnectionTester />
    </QueryClientProvider>
  );
}
