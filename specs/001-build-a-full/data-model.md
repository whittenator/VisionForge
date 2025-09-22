# Data Model: VisionForge MVP

Date: 2025-09-21

## Entities

- User(id, email, name, role, created_at)
- Project(id, name, description, owner_id, settings, created_at)
- Membership(id, project_id, user_id, role, created_at)
- Dataset(id, project_id, name, media_type[image|video], created_at)
- DatasetVersion(id, dataset_id, version, manifest_uri, stats_json, created_at)
- Asset(id, dataset_version_id, uri, thumb_uri, width, height, duration_ms?, metadata_json)
- AnnotationSchema(id, project_id, schema_json, color_map_json, created_at)
- Annotation(id, asset_id, schema_id, type[box|tag|track], data_json, author_id, status[draft|review|accepted|rejected], created_at, updated_at)
- Track(id, asset_id, track_id, data_json)  # for video tracks
- Experiment(id, project_id, name, params_json, dataset_version_id, metrics_json, status, started_at, finished_at, code_hash)
- Artifact(id, experiment_id, kind[weights|onnx|report], uri, size_bytes, checksum, metadata_json, stage[candidate|staging|production], version, created_at)
- ALRun(id, project_id, strategy[uncertainty|diversity|hybrid|class], params_json, created_at)
- ALItem(id, al_run_id, asset_id, priority, proposed_json, resolved_status[pending|accepted|edited|rejected], resolved_by, resolved_at)
- Job(id, type[ingest|extract|prelabel|uncertainty|embed|train|export], payload_json, status[pending|running|failed|succeeded], progress, logs_uri, created_at, updated_at)
- Audit(id, actor_id, entity, entity_id, action, diff_json, created_at)

## Relationships
- Project has many Datasets, Experiments, ALRuns
- Dataset has many DatasetVersions → each has many Assets
- Assets link to Annotations and Tracks
- Experiments produce Artifacts and are tied to a DatasetVersion
- ALRun proposes ALItems tied to Assets

## Validation Rules
- DatasetVersion is immutable after creation
- Annotation types must conform to project schema
- Artifact versions use semver and must be unique per experiment
- Stage transitions Candidate → Staging → Production require audit entry

## State Transitions (selected)
- Annotation: draft → review → accepted/rejected
- Job: pending → running → (succeeded|failed)
- Artifact stage: candidate → staging → production
