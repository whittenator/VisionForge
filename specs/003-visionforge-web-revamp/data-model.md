# Data Model — VisionForge Web Revamp

## Entities

- Workspace
  - id, name, logoUrl, region (US|EU [future]), createdAt, createdBy
  - Relationships: has many Projects; has many Members (User+Role)

- User
  - id, name, email (unique, verified), passwordHash, lastLoginAt, activeDevices
  - Relationships: belongs to many Workspaces via Membership (role)

- Role (enum)
  - Viewer | Annotator | Developer | Admin | Owner

- Membership
  - id, userId, workspaceId, role, invitedBy, invitedAt, acceptedAt

- Project
  - id, workspaceId, name, slug, description, status, tags[], archivedAt, createdAt, updatedAt
  - Relationships: has many Datasets, ExperimentRuns, ModelArtifacts, Members

- Dataset
  - id, projectId, name, description, classMapId, createdAt
  - Relationships: has many DatasetVersions; has many Assets

- ClassMap
  - id, projectId, classes[] (name, color, description)

- DatasetVersion
  - id, datasetId, version, notes, checksumSummary, assetCount, locked (bool), createdAt

- Asset
  - id, datasetId, versionId (nullable if latest), uri, mimeType, width, height, metadata, labelStatus, createdAt

- Annotation
  - id, assetId, type (box|polygon|line|point|classification), geometry, className, authorId, createdAt, history[]

- ExperimentRun
  - id, projectId, datasetVersionId, ownerId, status (queued|running|succeeded|failed), params, metrics, artifacts[], createdAt, completedAt

- ModelArtifact
  - id, projectId, runId, version, type (onnx, ...), checksum, sizeBytes, createdAt

- Invitation
  - id, workspaceId, email, role, token, expiresAt, invitedBy, acceptedAt

- AuditEvent
  - id, actorId, action, targetType, targetId, timestamp, context

- Notification
  - id, userId, type, title, body, readAt, createdAt

## Validation Rules

- Email must be unique and verified before privileged actions.
- DatasetVersion locked implies immutability for assets and annotations.
- Role-based access enforced across create/update/delete actions.
- Upload operations idempotent per client token to support retries.

## State Transitions (selected)

- ExperimentRun: queued → running → {succeeded|failed}; promote to ModelArtifact creates new version.
- Asset labelStatus: unlabelled → in_progress → labelled → in_review → approved/rejected.

## Provenance Links

- ModelArtifact → ExperimentRun → DatasetVersion → Dataset → Project → Workspace.
