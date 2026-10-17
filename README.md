# Tunisian Job Market Intelligence Platform

An incremental data engineering project that collects Tunisian job postings and prepares them for analysis of skills demand, locations, employment types, and disclosed salaries.

The project currently implements discovery and raw collection from Keejob. Transformation, dashboards, orchestration, streaming, and cloud deployment are planned.

## Current architecture

```text
Keejob listing pages
        │
        ▼
Discover candidate posting URLs
        │
        ▼
Discovery manifest — JSON
        │
        ▼
Fetch individual posting pages
        │
        ▼
Extract JobPosting JSON-LD
        │
        ├──► Bronze observations — JSON files
        │
        └──► Batch report — successes and failures
```

The current pipeline runs locally using Python and uv. It is an initial ingestion implementation, not yet a complete lakehouse.

## Data source

The implemented source is Keejob:

https://www.keejob.com/offres-emploi/

Listing pages use numbered pagination and a “Suivant” link. The discovery script follows that link and deduplicates candidate posting URLs.

For successfully collected postings, job information is extracted from an embedded JSON-LD object whose `@type` is `JobPosting`.

Public accessibility and crawler rules do not establish unrestricted reuse permission. Collection and reuse permissions remain to be clarified before ongoing deployment or redistribution.

## Setup

Requirements: Python and uv.

From the project directory:

```bash
uv sync
```

Dependencies include Requests and Beautiful Soup. Run the commands below from the project directory because saved paths are currently relative to it.

## Workflow

### 1. Inspect a posting

```bash
uv run inspect_job.py
```

Displays the response status, page heading, and embedded JSON-LD objects.

### 2. Discover posting URLs

```bash
uv run inspect_listing.py
```

Traverses listing pages and saves a discovery manifest containing:

- Source and listing URL.
- Scan start and completion timestamps.
- Number of pages inspected.
- Unique candidate URLs and their count.

### 3. Collect postings

Collect five postings by default:

```bash
uv run collect_from_manifest.py data/discovery/keejob/<manifest>.json
```

Select a batch size:

```bash
uv run collect_from_manifest.py data/discovery/keejob/<manifest>.json --limit 20
```

Collect the complete manifest:

```bash
uv run collect_from_manifest.py data/discovery/keejob/<manifest>.json --all
```

Requests are sequential, with a two-second pause between postings. This delay is a project setting, not a published source rate limit.

### 4. Inspect the collected data

```bash
uv run profile_bronze.py data/reports/keejob/<report>.json
uv run inspect_nested_fields.py data/reports/keejob/<report>.json
```

These scripts summarize field coverage, observed types, nested structures, and source job ID uniqueness. They do not perform full data validation.

## Storage

```text
data/
├── discovery/keejob/                  # Candidate URL manifests
├── bronze/keejob/
│   └── collection_date=YYYY-MM-DD/    # Individual observations
└── reports/keejob/                    # Completed batch reports
```

Each bronze record contains:

- `metadata`: source, requested URL, response URL, UTC collection timestamp, HTTP status, and content type.
- `payload`: the extracted JobPosting object, preserving its source field values and nested structure.

The stored payload is parsed JSON-LD. The complete HTML response is not retained.

Random UUID filenames identify stored observations. They do not identify jobs or prevent duplicate collection. The proposed posting key is the combination of source and source job ID.

Running collection again creates additional observations.

## Observed collection results

One discovery run traversed 52 pages and found 777 unique candidate URLs.

The corresponding full collection produced:

| Outcome | Count |
|---|---:|
| Saved observations | 683 |
| Missing JobPosting object | 93 |
| HTTP 404 | 1 |

Five sampled extraction failures returned HTTP 200, displayed an expired label, and contained no JobPosting object. This does not confirm that all 93 extraction failures were expired.

Among the 683 saved observations:

- All had a source job ID; none repeated within that batch.
- Salary objects appeared in 149 records.
- 46 location objects contained only a country.
- Two location objects contained locality and country without region.
- Company objects varied in whether they included profile URLs and logos.

Field presence does not establish completeness or correctness of nested values.

## Current limitations

- No scheduler, automatic resume, or retry strategy.
- Batch reports are saved only after normal loop completion.
- Failed extraction responses are not preserved for later replay.
- Expired pages are not explicitly classified.
- Individual JSON files may become inefficient at larger volumes.
- No tabular exploration interface yet.
- Source fields have not yet been transformed into a silver dataset.
- Data from one job board cannot represent the entire Tunisian job market.

## Next design decisions

Before implementing transformation:

1. Choose a convenient way to explore the collected observations using SQL, a spreadsheet, or both.
2. Decide whether to retain HTML responses for replay.
3. Define run identity, retry behavior, and duplicate handling.
4. Establish validation and transformation rules from the observed data.

Later milestones include analytical tables, orchestration, data quality checks, dashboards, and deployment. Technology choices will be documented as they are implemented.