import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { GraphEditorPage } from "../pages/GraphEditorPage";
import { GraphListPage } from "../pages/GraphListPage";
import { ProblemMapPage } from "../pages/ProblemMapPage";

export function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<GraphListPage />} />
        <Route path="/graphs/:graphId" element={<GraphEditorPage />} />
        <Route path="/graphs/:graphId/problem-map" element={<ProblemMapPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
