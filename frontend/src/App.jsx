import React, { useState, useEffect } from "react";
import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import { AuthProvider } from "@/services/auth-store";
import ProtectedRoute from "@/components/layout/ProtectedRoute";
import LoginPage from "@/pages/auth/Login";
import AppShell from "@/components/layout/AppShell";
import AnnotatorPage from "./pages/annotate/Annotator";
import AdminUsersPage from "./pages/admin/users";
import ProjectsIndex from "./pages/projects/index";
import ProjectsCreate from "./pages/projects/create";
import ProjectDashboard from "./pages/projects/[projectId]/index";
import DatasetUpload from "./pages/datasets/upload";
import DatasetVersion from "./pages/datasets/version";
import DatasetsIndex from "./pages/datasets/index";
import ExperimentsIndex from "./pages/experiments/index";
import ExperimentsNew from "./pages/experiments/new";
import ExperimentDetail from "./pages/experiments/[runId]";
import ArtifactsIndex from "./pages/artifacts/index";
import ArtifactsExport from "./pages/artifacts/export";
import { apiGet } from "@/services/api";
import Spinner from "@/components/ui/Spinner";

function HomeDashboard() {
  const [stats, setStats] = useState({ projects: null, datasets: null, models: null });
  const [statsLoading, setStatsLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      apiGet("/api/projects"),
      apiGet("/api/datasets"),
      apiGet("/api/artifacts/models"),
    ])
      .then(([projects, datasets, models]) => {
        setStats({
          projects: Array.isArray(projects) ? projects.length : 0,
          datasets: Array.isArray(datasets) ? datasets.length : 0,
          models: Array.isArray(models) ? models.length : 0,
        });
      })
      .catch(console.error)
      .finally(() => setStatsLoading(false));
  }, []);

  return (
    <div className="grid gap-6 md:grid-cols-[1.2fr_0.8fr] items-start">
      <div className="space-y-4">
        <h1 className="text-3xl md:text-4xl font-semibold tracking-tight">
          Build vision products faster
        </h1>
        <p className="text-muted-foreground">
          Manage datasets, annotate frames, and iterate on models with an integrated workflow.
        </p>
        <div className="flex gap-3">
          <Link
            className="inline-flex h-10 items-center rounded-md bg-primary px-4 text-primary-foreground hover:opacity-90"
            to="/projects/create"
          >
            New Project
          </Link>
          <Link
            className="inline-flex h-10 items-center rounded-md border px-4 hover:bg-muted"
            to="/datasets/upload"
          >
            Upload Dataset
          </Link>
        </div>
      </div>
      <div className="rounded-xl border bg-card p-6 shadow-sm">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm text-muted-foreground">Active Projects</div>
            <div className="text-2xl font-semibold">
              {statsLoading ? <Spinner /> : stats.projects ?? 0}
            </div>
          </div>
          <div className="size-10 rounded-full bg-primary/10" />
        </div>
        <div className="mt-6 grid grid-cols-3 gap-4 text-center">
          <div>
            <div className="text-xl font-semibold">
              {statsLoading ? <Spinner /> : stats.datasets ?? 0}
            </div>
            <div className="text-xs text-muted-foreground">Datasets</div>
          </div>
          <div>
            <div className="text-xl font-semibold text-muted-foreground text-sm">—</div>
            <div className="text-xs text-muted-foreground">Assets</div>
          </div>
          <div>
            <div className="text-xl font-semibold">
              {statsLoading ? <Spinner /> : stats.models ?? 0}
            </div>
            <div className="text-xs text-muted-foreground">Models</div>
          </div>
        </div>
      </div>
    </div>
  );
}

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
                  <HomeDashboard />
                </ProtectedRoute>
              }
            />
            {/* Projects */}
            <Route path="/projects" element={<ProtectedRoute><ProjectsIndex /></ProtectedRoute>} />
            <Route path="/projects/create" element={<ProtectedRoute><ProjectsCreate /></ProtectedRoute>} />
            <Route path="/projects/:projectId" element={<ProtectedRoute><ProjectDashboard /></ProtectedRoute>} />
            {/* Datasets */}
            <Route path="/datasets" element={<ProtectedRoute><DatasetsIndex /></ProtectedRoute>} />
            <Route path="/datasets/upload" element={<ProtectedRoute><DatasetUpload /></ProtectedRoute>} />
            <Route path="/datasets/version" element={<ProtectedRoute><DatasetVersion /></ProtectedRoute>} />
            {/* Experiments */}
            <Route path="/experiments" element={<ProtectedRoute><ExperimentsIndex /></ProtectedRoute>} />
            <Route path="/experiments/new" element={<ProtectedRoute><ExperimentsNew /></ProtectedRoute>} />
            <Route path="/experiments/runs/:runId" element={<ProtectedRoute><ExperimentDetail /></ProtectedRoute>} />
            {/* Artifacts */}
            <Route path="/artifacts" element={<ProtectedRoute><ArtifactsIndex /></ProtectedRoute>} />
            <Route path="/artifacts/export/:modelId" element={<ProtectedRoute><ArtifactsExport /></ProtectedRoute>} />
            {/* Annotate */}
            <Route path="/annotate/:assetId" element={<ProtectedRoute><AnnotatorPage /></ProtectedRoute>} />
            {/* Admin */}
            <Route path="/admin/users" element={<ProtectedRoute><AdminUsersPage /></ProtectedRoute>} />
          </Routes>
        </AppShell>
      </AuthProvider>
    </BrowserRouter>
  );
}
