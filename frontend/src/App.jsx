import React from "react";
import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import { AuthProvider } from "@/services/auth-store";
import ProtectedRoute from "@/components/layout/ProtectedRoute";
import LoginPage from "@/pages/auth/Login";
import AppShell from "@/components/layout/AppShell";
import AnnotatorPage from "./pages/annotate/Annotator";
import AdminUsersPage from "./pages/admin/Users";
import ProjectsIndex from "./pages/projects/index";
import ProjectsCreate from "./pages/projects/create";
import ProjectDashboard from "./pages/projects/[projectId]/index";
import DatasetUpload from "./pages/datasets/upload";
import DatasetVersion from "./pages/datasets/version";
import ExperimentsIndex from "./pages/experiments/index";
import ExperimentsNew from "./pages/experiments/new";
import ArtifactsIndex from "./pages/artifacts/index";
import ArtifactsExport from "./pages/artifacts/export";

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppShell>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <div className="grid gap-6 md:grid-cols-[1.2fr_0.8fr] items-start">
                <div className="space-y-4">
                  <h1 className="text-3xl md:text-4xl font-semibold tracking-tight">Build vision products faster</h1>
                  <p className="text-muted-foreground">Manage datasets, annotate frames, and iterate on models with an integrated workflow.</p>
                  <div className="flex gap-3">
                    <Link className="inline-flex h-10 items-center rounded-md bg-primary px-4 text-primary-foreground hover:opacity-90" to="/projects/create">New Project</Link>
                    <Link className="inline-flex h-10 items-center rounded-md border px-4 hover:bg-muted" to="/datasets/upload">Upload Dataset</Link>
                  </div>
                </div>
                <div className="rounded-xl border bg-card p-6 shadow-sm">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-sm text-muted-foreground">Active Projects</div>
                      <div className="text-2xl font-semibold">3</div>
                    </div>
                    <div className="size-10 rounded-full bg-primary/10" />
                  </div>
                  <div className="mt-6 grid grid-cols-3 gap-4 text-center">
                    <div><div className="text-xl font-semibold">12</div><div className="text-xs text-muted-foreground">Datasets</div></div>
                    <div><div className="text-xl font-semibold">842</div><div className="text-xs text-muted-foreground">Assets</div></div>
                    <div><div className="text-xl font-semibold">5</div><div className="text-xs text-muted-foreground">Models</div></div>
                  </div>
                </div>
                  </div>
                </ProtectedRoute>
              }
            />
          {/* Frontend MVP routes (T051–T058) */}
            <Route path="/projects" element={<ProtectedRoute><ProjectsIndex /></ProtectedRoute>} />
            <Route path="/projects/create" element={<ProtectedRoute><ProjectsCreate /></ProtectedRoute>} />
            <Route path="/projects/:projectId" element={<ProtectedRoute><ProjectDashboard /></ProtectedRoute>} />
            <Route path="/datasets/upload" element={<ProtectedRoute><DatasetUpload /></ProtectedRoute>} />
            <Route path="/datasets/version" element={<ProtectedRoute><DatasetVersion /></ProtectedRoute>} />
            <Route path="/experiments" element={<ProtectedRoute><ExperimentsIndex /></ProtectedRoute>} />
            <Route path="/experiments/new" element={<ProtectedRoute><ExperimentsNew /></ProtectedRoute>} />
            <Route path="/artifacts" element={<ProtectedRoute><ArtifactsIndex /></ProtectedRoute>} />
            <Route path="/artifacts/export" element={<ProtectedRoute><ArtifactsExport /></ProtectedRoute>} />
            <Route path="/annotate/:assetId" element={<ProtectedRoute><AnnotatorPage /></ProtectedRoute>} />
            <Route path="/admin/users" element={<ProtectedRoute><AdminUsersPage /></ProtectedRoute>} />
          </Routes>
        </AppShell>
      </AuthProvider>
    </BrowserRouter>
  );
}
