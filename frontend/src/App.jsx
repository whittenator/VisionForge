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

function StatReadout({ label, value, loading, href }) {
  return (
    <div className="border border-[var(--hud-border-default)] bg-[var(--hud-surface)] p-3 flex flex-col gap-1">
      <div className="label-overline">{label}</div>
      <div className="text-2xl font-semibold font-mono text-[var(--hud-text-data)]">
        {loading ? <Spinner size={18} /> : value ?? 0}
      </div>
      {href && (
        <Link
          to={href}
          className="text-[0.6875rem] font-mono text-[var(--hud-accent)] hover:underline underline-offset-2 mt-1"
        >
          VIEW →
        </Link>
      )}
    </div>
  );
}

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
    <div className="space-y-6">
      {/* Hero section */}
      <div className="border border-[var(--hud-border-default)] bg-[var(--hud-surface)] p-6">
        {/* Top label */}
        <div className="label-overline mb-3">// VisionForge · Computer Vision Platform</div>

        <div className="grid gap-6 md:grid-cols-[1fr_auto] items-center">
          <div className="space-y-3">
            <h1 className="text-xl font-semibold tracking-tight text-[var(--hud-text-primary)]">
              Manage datasets, annotate frames,<br />and iterate on models.
            </h1>
            <p className="text-xs text-[var(--hud-text-muted)] max-w-md">
              End-to-end CV workflow: ingest → annotate → train → export → deploy.
            </p>
            <div className="flex gap-2 pt-1">
              <Link
                to="/projects/create"
                className="inline-flex items-center h-8 px-3 text-xs font-mono font-medium bg-[var(--hud-accent)] text-[oklch(0.10_0.008_240)] border border-[var(--hud-accent)] hover:bg-[var(--hud-accent-hover)] transition-colors tracking-wide"
              >
                + NEW PROJECT
              </Link>
              <Link
                to="/datasets/upload"
                className="inline-flex items-center h-8 px-3 text-xs font-mono text-[var(--hud-text-secondary)] border border-[var(--hud-border-strong)] hover:border-[var(--hud-border-accent)] hover:bg-[var(--hud-elevated)] transition-colors tracking-wide"
              >
                UPLOAD DATASET
              </Link>
            </div>
          </div>

          {/* System status panel */}
          <div className="border border-[var(--hud-border-default)] bg-[var(--hud-inset)] px-4 py-3 min-w-[160px]">
            <div className="label-overline mb-2">System Status</div>
            <div className="space-y-1.5 text-xs font-mono">
              <div className="flex items-center justify-between gap-4">
                <span className="text-[var(--hud-text-muted)]">API</span>
                <span className="text-[var(--hud-success-text)]">● ONLINE</span>
              </div>
              <div className="flex items-center justify-between gap-4">
                <span className="text-[var(--hud-text-muted)]">QUEUE</span>
                <span className="text-[var(--hud-success-text)]">● ONLINE</span>
              </div>
              <div className="flex items-center justify-between gap-4">
                <span className="text-[var(--hud-text-muted)]">STORAGE</span>
                <span className="text-[var(--hud-success-text)]">● ONLINE</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Stats row */}
      <div>
        <div className="label-overline mb-2">Platform Overview</div>
        <div className="grid grid-cols-3 gap-px bg-[var(--hud-border-default)]">
          <StatReadout label="Projects"  value={stats.projects} loading={statsLoading} href="/projects"    />
          <StatReadout label="Datasets"  value={stats.datasets} loading={statsLoading} href="/datasets"    />
          <StatReadout label="Models"    value={stats.models}   loading={statsLoading} href="/artifacts"   />
        </div>
      </div>

      {/* Quick nav grid */}
      <div>
        <div className="label-overline mb-2">Quick Access</div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-px bg-[var(--hud-border-default)]">
          {[
            { to: '/projects',    label: 'PROJECTS',    desc: 'Manage project workspaces'      },
            { to: '/datasets',   label: 'DATASETS',    desc: 'Browse and upload datasets'     },
            { to: '/experiments', label: 'EXPERIMENTS', desc: 'Training runs and metrics'      },
            { to: '/artifacts',  label: 'ARTIFACTS',   desc: 'Model exports and lineage'      },
          ].map(({ to, label, desc }) => (
            <Link
              key={to}
              to={to}
              className="bg-[var(--hud-surface)] px-4 py-3 hover:bg-[var(--hud-elevated)] transition-colors group"
            >
              <div className="text-xs font-mono font-semibold tracking-widest text-[var(--hud-text-secondary)] group-hover:text-[var(--hud-accent)] transition-colors">
                {label}
              </div>
              <div className="text-[0.6875rem] text-[var(--hud-text-muted)] mt-0.5">{desc}</div>
            </Link>
          ))}
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
