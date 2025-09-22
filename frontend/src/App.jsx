import React from "react";
import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
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
      <AppShell>
        <Routes>
          <Route
            path="/"
            element={
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
            }
          />
          {/* Frontend MVP routes (T051–T058) */}
          <Route path="/projects" element={<ProjectsIndex />} />
          <Route path="/projects/create" element={<ProjectsCreate />} />
          <Route path="/projects/:projectId" element={<ProjectDashboard />} />
          <Route path="/datasets/upload" element={<DatasetUpload />} />
          <Route path="/datasets/version" element={<DatasetVersion />} />
          <Route path="/experiments" element={<ExperimentsIndex />} />
          <Route path="/experiments/new" element={<ExperimentsNew />} />
          <Route path="/artifacts" element={<ArtifactsIndex />} />
          <Route path="/artifacts/export" element={<ArtifactsExport />} />
          <Route path="/annotate/:assetId" element={<AnnotatorPage />} />
          <Route path="/admin/users" element={<AdminUsersPage />} />
        </Routes>
      </AppShell>
    </BrowserRouter>
  );
}
