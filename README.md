# Tunisian Job Market Intelligence Platform

An educational data engineering project that collects Keejob postings for the Tunisian market and produces analytical datasets about company accounts, governorates, and disclosed salaries.

The pipeline runs locally or in a Docker container. Discovery manifests, source observations, execution reports, and analytical datasets are stored directly in MinIO. pandas performs transformation and aggregation; DuckDB queries remote Parquet for interactive analysis and Apache Superset dashboards. PostgreSQL stores Superset's application metadata. A full-batch container run has completed successfully. Counts depend on the selected manifest and source availability.

## Current architecture

```text
Keejob listing pages
        ↓
Discovery manifest + resumable discovery checkpoint in MinIO
        ↓
Posting collection → Bronze JSON observations + collection report
        ↓
Silver transformation + quality checks
        ↓
Silver Parquet + transformation execution report
        ↓
Gold calculations → Four run-specific Parquet datasets
        ↓
Published gold manifest
        ├── Local notebooks → pandas / DuckDB SQL analysis
        └── Superset → Embedded DuckDB → Gold Parquet in MinIO

Browser → Superset website
              └── PostgreSQL: users, connections, datasets, charts, dashboards
```

`jobmarket-run` connects all four stages sequentially and writes a pipeline execution report. Each stage also has its own command. The stages pass object keys to one another; manual synchronization and local intermediate files are no longer required.

This is object storage organized into bronze, silver, and gold layers, **not yet a managed lakehouse**. MinIO stores ordinary JSON and Parquet objects; Iceberg or Delta Lake table management is not implemented.

## Project layout

```text
.
├── pipeline/
│   ├── pyproject.toml       # ETL package and runtime dependencies
│   ├── uv.lock
│   ├── .python-version
│   ├── .dockerignore       # Filters the pipeline build context
│   ├── README.md
│   └── src/data_engineering/
│       ├── pipeline.py     # Sequential runner and execution report
│       ├── ingestion/      # Discovery, collection, bronze publication
│       ├── silver/         # Cleaning, validation, publication
│       ├── gold/           # Analytical models and publication
│       └── storage/        # MinIO connection and object operations
├── exploration/
│   ├── pyproject.toml       # pandas, DuckDB, storage and notebook dependencies
│   ├── uv.lock
│   ├── .python-version
│   ├── README.md
│   ├── notebooks/          # Empty notebooks reserved for future exploration
│   └── src/jobmarket_exploration/
│       └── storage/        # MinIO access and DuckDB SQL helpers
├── docker/
│   ├── minio/Dockerfile
│   ├── pipeline/Dockerfile
│   └── superset/
│       ├── Dockerfile
│       ├── requirements.txt
│       ├── superset_config.py
│       └── gold_connection.py
├── docker-compose.yml
├── .env.example
└── README.md
```

Pipeline and exploration are independent Python projects, each with its own lockfile
and virtual environment. The pipeline has no DuckDB or Jupyter dependency.
Exploration uses its own storage helpers and does not import the pipeline package.
Storage helpers currently exist in both packages; changes to shared behavior need
review in both places. The three notebooks are intentionally empty.

There is no root Python project or local `data/` directory. Active datasets live
in MinIO. Compose uses the stable project name `dataengineering` so renaming the
checkout does not change its container or volume names.

## Setup and storage

Run commands from the project root. Local Python use requires Python 3.12 or newer and uv; container execution requires Docker with Compose.

Copy the configuration template, then edit `.env` with your local credentials:

```bash
cp .env.example .env
```

Do not overwrite an existing configured `.env`. Its required settings are:

```dotenv
MINIO_ENDPOINT=http://127.0.0.1:19000
MINIO_BUCKET=tunisian-jobs
MINIO_ROOT_USER=jobmarket
MINIO_ROOT_PASSWORD=replace_with_your_local_password
POSTGRES_DB=superset
POSTGRES_USER=superset
POSTGRES_PASSWORD=replace_with_a_generated_password
SUPERSET_SECRET_KEY=replace_with_a_generated_secret
GOLD_MANIFEST_KEY=gold/keejob/replace_with_your_batch_id/manifest.json
```

The bucket is configurable; object keys below are relative to it. Replace the gold manifest placeholder with an existing published manifest key, without the bucket or `s3://` prefix. The environment variables above are required by the current Compose file, including when selecting an individual service. Credentials are excluded from Git and the pipeline Docker build context. The pipeline build context is `pipeline/`, filtered by `pipeline/.dockerignore`; its Dockerfile copies that directory into `/app`. Exploration and root credentials are outside this context. Superset's build context is only `docker/superset/` and does not include the pipeline package.

Local installation is optional when running ETL in Docker. To install the pipeline
on the host, run from the repository root:

```bash
cd pipeline
uv sync --locked
cd ..
```

Exploration has separate setup instructions below.

Start MinIO and build the pipeline image:

```bash
docker compose up -d minio
docker compose build pipeline
```

- `up` creates or starts the selected service; `-d` leaves it running in the background.
- `build pipeline` builds the application image without running a collection.
- Compose automatically reads `docker-compose.yml` and takes configuration values from the project's `.env`.

MinIO is built from a pinned source release. The pipeline image uses Python 3.12 and installs only the dependencies declared in `pipeline/pyproject.toml`, using `pipeline/uv.lock`. pandas and PyArrow remain runtime dependencies because ETL uses them. Superset installs its DuckDB dependencies independently.

| Access location | Endpoint |
|---|---|
| Python running on the host | `http://127.0.0.1:19000` |
| MinIO browser console | [http://127.0.0.1:19001](http://127.0.0.1:19001) |
| Pipeline and Superset containers on the Compose network | `http://minio:9000` |
| Superset website | [http://127.0.0.1:8088](http://127.0.0.1:8088) |
| Superset metadata database, internal only | `superset-db:5432` |

Compose injects the internal endpoint into the pipeline container. The pipeline sends requests to MinIO and needs no published port. Host port bindings use `127.0.0.1`, so this setup does not expose MinIO to other machines. The named `minio_data` volume preserves objects when containers are replaced; deleting the volume deletes its stored data.

The pipeline service has a `jobs` profile, so ordinary storage startup does not launch collection. Explicit `docker compose run` commands select it when needed. Its default command prints collection help.

Boto3 uses Signature Version 4 and path-style bucket addressing. The signing region is `us-east-1`; this does not move storage to AWS. Objects remain where MinIO runs.

## Superset dashboards

The BI stack has separate responsibilities:

| Component | Responsibility |
|---|---|
| MinIO | Stores the original JSON and analytical Parquet objects |
| Pipeline | Collects, transforms, validates, and publishes data; exits after execution |
| Superset | Serves the dashboard website and remembers dataset/chart definitions |
| DuckDB inside Superset | Executes SQL over gold Parquet in MinIO; no separate DuckDB server |
| PostgreSQL 16 | Persists Superset metadata, not job postings or gold tables |

The `superset-db` service uses the official PostgreSQL image, without publishing a host port. It is separate from any PostgreSQL installation on the host. The `superset_db_data` and `superset_home` volumes preserve database and application files when containers are replaced. Do not delete these volumes if you want to retain the setup.

### First-time initialization

Generate separate values for `POSTGRES_PASSWORD` and `SUPERSET_SECRET_KEY` by running this command twice and saving the results in `.env`:

```bash
openssl rand -hex 32
```

Keep the secret key stable: Superset uses it for session signing and encryption of saved credentials. PostgreSQL's initialization environment variables create the database/user only on an empty data volume; changing `.env` does not reset an existing database password.

Build and initialize in this order:

```bash
docker compose build superset
docker compose up -d minio superset-db
docker compose run --rm superset superset db upgrade
docker compose run --rm superset superset fab create-admin
docker compose run --rm superset superset init
docker compose up -d superset
```

`db upgrade` creates or migrates the metadata tables; `create-admin` prompts for the website administrator account; `init` synchronizes built-in roles and permissions. These credentials are independent of PostgreSQL and MinIO credentials. Normal subsequent startup uses `docker compose up -d minio superset-db superset`. Superset waits for PostgreSQL's health check; MinIO must also be available when an analytical connection is opened.

Open the website and register a database connection named **Tunisian Job Market**, using the DuckDB backend and this SQLAlchemy URI:

```text
duckdb:///:memory:
```

Enable **Expose in SQL Lab**. Register the four gold views under **Datasets → + Dataset**, selecting schema **`memory.main`**:

- `company_posting_counts`
- `governorate_posting_counts`
- `salary_summary`
- `salary_postings`

Superset labels these named views as physical datasets; registration does not copy their data into PostgreSQL. If database/security menus are missing after initialization, run `docker compose exec superset superset init`, then log out and back in with the administrator account.

### How the gold connection works

`superset_config.py` registers a SQLAlchemy connection hook from `gold_connection.py`. For each newly opened DuckDB connection, it installs/loads `httpfs`, creates a connection-local S3 secret from environment variables, reads `GOLD_MANIFEST_KEY`, and checks its publication status and bucket. It then creates the four SQL views using the exact Parquet keys in that manifest. PostgreSQL connections are left unchanged. Each DuckDB connection is configured for two threads and a 1 GB memory limit; this is not a container-wide memory limit.

The catalog and views live in memory and are recreated for new connections. The Parquet files remain in MinIO. Initial extension installation can require internet access, and queries require MinIO to be available. The current local configuration supplies MinIO root credentials to Superset; a deployment should replace these with credentials restricted to the required read operations.

The selected manifest is explicit: there is no global latest-batch pointer or automatic switch after a new pipeline run. To select another batch, change `GOLD_MANIFEST_KEY` in `.env` and run `docker compose up -d superset`. New connections read the selected manifest; a manifest overwritten at the same key is picked up by new connections, not necessarily existing ones. Chart caches and separate connections mean this is not a dashboard-wide snapshot transaction.

Rebuild Superset after changing its Python files or requirements:

```bash
docker compose build superset
docker compose up -d superset
```

### Initial chart definitions

Create a **Tunisian Job Market** dashboard and save charts with these definitions:

| Chart | Dataset | Category | Metric | Selection |
|---|---|---|---|---|
| Top 10 companies by listed postings | `company_posting_counts` | `company_name` | `SUM(posting_count)` | Descending metric, 10 rows |
| Listed postings by governorate | `governorate_posting_counts` | `governorate` | `SUM(posting_count)` | Descending metric, include all regions |

Use horizontal bars, value labels, and no legend for these single-metric charts. Do not use `COUNT(*)`: gold rows already contain aggregated posting counts. Grouping by company name merges distinct company profiles with identical names; use `company_url` as an additional grouping identity if those must be distinguished. Keep `Unknown` governorates visible. Salary charts must keep currency and period separate.

Connection and dataset registration have been exercised in the local UI; comprehensive integration verification remains pending. Dashboard definitions are currently stored in PostgreSQL and are not exported/versioned in this repository, so a new installation requires the UI registration and chart creation above.

## Run the complete pipeline

A small run scans one listing page and attempts five postings:

```bash
docker compose run --rm pipeline jobmarket-run --max-pages 1 --limit 5
```

- `run` starts a container for the supplied command.
- `--rm` removes that container afterward; the image and MinIO volume remain.
- `--max-pages 1` caps discovery at one listing page.
- `--limit 5` caps posting collection at five URL attempts, not five successes.

For complete discovery and collection:

```bash
docker compose run --rm pipeline jobmarket-run --all
```

**Without `--max-pages`, discovery scans all available listing pages. Without `--all` or `--limit`, collection attempts only five URLs.** `--limit` does not limit listing-page discovery. Collection selects the first URLs from the sorted manifest; it is not random sampling or selection by newest posting.

Reuse an existing discovery manifest to skip scanning listing pages. At the prompt, paste the manifest key printed by an earlier run, without the `s3://bucket/` prefix:

```bash
read -r -p 'Discovery manifest key: ' manifest_key
docker compose run --rm pipeline jobmarket-run --manifest-key "$manifest_key" --all
```

`--manifest-key` cannot be combined with `--max-pages` or `--resume-discovery`. `--all` and `--limit` are mutually exclusive. Page and posting limits must be positive integers.

The same command runs without the pipeline container, from the repository root:

```bash
cd pipeline
uv run jobmarket-run --max-pages 1 --limit 5
cd ..
```

After source or dependency changes, rebuild with `docker compose build pipeline` before using the container again. A successful execution prints both the pipeline report key and the published gold manifest key.

## Discovery retries, checkpoints, and resume

Discovery follows Keejob's visible “Suivant” link, accepts posting URL paths containing a numeric ID, strips query strings/fragments, and deduplicates candidates across pages. It fails on repeated page URLs, redirects to previously visited pages, or pages with no candidate posting URLs.

`candidates` counts distinct posting URLs on a page; `new` excludes URLs already seen. For example, 17 candidates and 15 new means two were already collected in the discovery set.

Discovery requests use a 10-second connection timeout and a 30-second read timeout. Timeouts and connection errors receive at most three attempts, with two- and four-second waits before retries. HTTP error responses are raised immediately; there is no retry policy for 429 or 5xx responses. Normal discovery pages also have a two-second pause between requests. These are project settings, not a claimed source-approved rate limit.

A checkpoint is saved before scanning and after every successful page. It contains accumulated URLs, visited pages, per-page history, and `next_url`. A final manifest is published only after a normal stop: `no_next_page` or `page_limit`.

To resume, paste a checkpoint key printed by discovery or recorded in the pipeline report:

```bash
read -r -p 'Discovery checkpoint key: ' checkpoint_key
docker compose run --rm pipeline jobmarket-run --resume-discovery "$checkpoint_key" --limit 5
```

This continues discovery until pagination ends, then collects up to five postings and runs silver and gold. Add `--all` instead of `--limit 5` to collect every URL in the resulting manifest.

`--max-pages` is a **total cap including restored pages**: resuming after one page with `--max-pages 2` fetches one more page. With pages remaining, the cap must exceed the completed count. A checkpoint with `next_url: null` needs no more requests.

Resume writes to a new checkpoint and records `resumed_from`; the original checkpoint is preserved. It is explicit, not automatic, and applies to discovery only. Listings can change while scanning is paused, so resuming does not recreate a frozen website snapshot.

## Run individual stages

For the local commands in this section, first run `cd pipeline` from the repository root; return with `cd ..` before running Compose commands. Each stage has an installed command and reusable function. The functions return the key needed by the next stage:

```python
manifest_key = run_discovery(client)
report_key = run_collection(client, manifest_key, limit=5)
silver_key = run_silver(client, report_key)
gold_manifest_key = run_gold(client, silver_key)
```

These functions live under `pipeline/src/data_engineering/` in `ingestion/discover.py`, `ingestion/collect.py`, `silver/pipeline.py`, and `gold/pipeline.py`. In Python, `limit=None` means all URLs; commands use `--all`.

Discover one page:

```bash
uv run jobmarket-discover --max-pages 1
```

Collect from its manifest:

```bash
read -r -p 'Discovery manifest key: ' manifest_key
uv run jobmarket-collect "$manifest_key" --limit 5
```

Collection requests each selected posting sequentially, with a two-second pause between postings and a 30-second request timeout. It extracts a top-level `JobPosting` object from embedded JSON-LD and saves the parsed payload unchanged alongside source metadata. It does not preserve the full HTML page.

Handled extraction and request failures are listed in the collection report. HTTP 401, 403, and 429 stop the batch; storage errors propagate. Collection does not use discovery's retries or checkpoints. The report is written after the loop, so a fatal error or interruption can leave already saved bronze objects without a completed collection report.

Transform the successful observations referenced by a collection report, then publish gold:

```bash
read -r -p 'Collection report key: ' report_key
uv run jobmarket-silver "$report_key"
read -r -p 'Silver Parquet key: ' silver_key
uv run jobmarket-gold "$silver_key"
```

Silver accepts new `bronze_key` entries and historical `bronze_path` entries, translating old `data/bronze/...` references into object keys. Reprocessing the same collection report replaces its silver object and creates a new transformation report.

## Stored objects and execution reports

The following is a key layout, not a set of shell commands. Each ID is generated during execution; the silver batch ID is the collection report's filename stem.

```text
bucket/
├── discovery/keejob/{manifest_id}.json
├── checkpoints/discovery/keejob/{checkpoint_id}.json
├── bronze/keejob/collection_date=YYYY-MM-DD/{observation_id}.json
├── silver/keejob/{batch_id}.parquet
├── reports/
│   ├── keejob/{collection_report_id}.json
│   ├── transformation/keejob/{execution_id}.json
│   └── pipeline/keejob/{pipeline_run_id}.json
└── gold/keejob/{batch_id}/
    ├── manifest.json
    └── runs/{gold_run_id}/
        ├── company_posting_counts.parquet
        ├── governorate_posting_counts.parquet
        ├── salary_summary.parquet
        └── salary_postings.parquet
```

A bronze observation's UUID identifies a collection event, not a job. `metadata.source` and `payload.identifier.value` identify a source posting; URLs and collection timestamps provide additional traceability. Recollection produces another observation rather than overwriting the previous one. Cross-batch history and deduplication are not yet modeled.

Use the report matching the problem:

| Object | What to inspect |
|---|---|
| Pipeline report | `status`, `stage`, `error`, `outputs`, discovery checkpoint/resume keys, configured limits |
| Discovery checkpoint | Completed pages, next URL, accumulated URLs, per-page new/repeated counts |
| Collection report | Manifest key, `successful_count`, `failed_count`, `saved_records`, `failures` |
| Transformation report | Input/excluded/output counts, quality checks, error, output key |
| Gold manifest | Complete published run, input silver key/count, excluded company count, dataset keys and row counts |

The pipeline report's `outputs` contains `discovery_manifest_key`, `collection_report_key`, `silver_key`, and `gold_manifest_key`. Keys stay `null` until the corresponding stage returns successfully. A report with `status: success` means the stages completed; it does not mean every candidate posting was collected successfully.

Pipeline and transformation reports are attempted when execution ends, including ordinary exceptions. They are not live status records; abrupt termination or unavailable storage can prevent reporting. Silver report-writing failures may mask an earlier exception, while the pipeline report writer preserves it. There is no automatic stage retry or full-pipeline resume.

Gold uploads all four outputs under a new run prefix, then updates `manifest.json` last. Consumers should read that manifest once and use its dataset keys. Listing every Parquet object under `gold/` would mix executions and any historical migrated outputs. A batch with no disclosed salaries legitimately publishes empty salary datasets.

This is a publication convention, not a multi-object transaction. Failed uploads can leave unreferenced objects; checkpoints, reports, and datasets are separate writes. Concurrent publishers are not coordinated.

## Exploration with pandas and SQL

From the repository root, install the independent exploration environment and start Jupyter:

```bash
cd exploration
uv sync --locked
uv run jupyter lab
```

Choose `exploration/.venv` as the Python environment when using another notebook
editor. The notebooks are intentionally empty placeholders. Read current datasets
from MinIO using the helpers below; no local data folder is required. Both Python
projects load the repository-root `.env` through python-dotenv. Host Python uses
`http://127.0.0.1:19000`; containers receive `http://minio:9000` from Compose.

`storage.s3.read_json(client, key)` reads an object as Python data. `read_parquet(client, key)` downloads the complete small Parquet object into a pandas DataFrame. `storage.query.query_parquet(session, key, sql)` instead lets DuckDB query remote Parquet through S3 and returns the query result as a DataFrame. SQL refers to that object using the temporary view name `dataset`.

For example, paste a published gold manifest key when prompted:

```python
from jobmarket_exploration.storage.connection import create_client, create_session
from jobmarket_exploration.storage.query import query_parquet
from jobmarket_exploration.storage.s3 import read_json

session = create_session()
client = create_client(session)
manifest_key = input("Published gold manifest key: ").strip()
manifest = read_json(client, manifest_key)

if manifest["status"] != "complete":
    raise ValueError("The selected gold run is not complete.")

company_key = manifest["datasets"]["company_posting_counts"]["key"]
companies = query_parquet(
    session,
    company_key,
    """
    SELECT company_name, posting_count
    FROM dataset
    ORDER BY posting_count DESC, company_name ASC
    LIMIT 10
    """,
)
companies
```

The helper opens one in-memory DuckDB connection per call and installs/loads `httpfs`; the initial extension download may need internet. It uses the Boto3 session credentials and configured endpoint; temporary AWS session tokens are not yet supported. DuckDB runs inside Python, without a shared SQL server.

For a pandas preview, import `read_parquet` from
`jobmarket_exploration.storage.s3` and call `read_parquet(client, key)` in a
notebook. The former `jobmarket-read` and `jobmarket-upload` commands have been
removed; object access is available through the Python helpers.

## Transformation rules and business measures

Silver keeps only records whose source country equals `TN`; bronze payloads remain unchanged. It:

- Removes JSON-LD type/context fields, company logos, applicant-location requirements, and selected HTTP diagnostics.
- Retains source, posting ID, source URL, collection time, and available remote-work information.
- Parses publication/expiry as timezone-free datetimes because the source supplies no timezone, and collection time as UTC-aware.
- Rejects missing required dates and expiry earlier than publication.
- Converts HTML descriptions to plain text and normalizes whitespace.
- Preserves salary bounds and locality names; geographic mappings are deferred.

Quality checks reject empty silver data, missing or blank identity/content fields, duplicate `(source, job_id)` identities within the batch, and disclosed salary bounds that are nonnumeric, infinite, negative, or reversed. Missing salaries are allowed. Validation must pass before silver is saved.

Exploration has also exposed suspicious positive salary bounds, including `1–2`,
`9.998–9.999`, and unusually wide ranges. These currently pass validation.
Extrema should be interpreted cautiously until source values are investigated and
explicit cleaning rules are agreed. No arbitrary salary cutoff or null conversion
has been implemented.

| Gold dataset | Grain and measure |
|---|---|
| `company_posting_counts` | One source × company profile URL; distinct posting count |
| `governorate_posting_counts` | One source × source-reported governorate; distinct posting count, with missing/blank regions as `Unknown` |
| `salary_summary` | One source × currency × salary period; disclosed posting count, lowest minimum bound, highest maximum bound, total source postings, disclosure percentage |
| `salary_postings` | One posting with at least one disclosed salary bound, including its source URL |

Anonymous employers and accounts without usable company names/profile URLs are excluded from company rankings, but remain eligible for geography and salary analysis. Company accounts may represent recruitment agencies rather than final employers. Gold checks reconcile the aggregations with their expected input coverage; disclosed salaries require currency and salary period. The disclosure percentage's denominator is all silver postings for the source, not just the currency/period group.

These measures describe listed postings, not completed hires or a guaranteed number of vacancies. Salary extrema are advertised bounds, not observed earnings. Different currencies and periods are not combined. Missing salary values are not zero, and disclosed pay does not represent every posting. One source and a snapshot of available postings do not represent the entire Tunisian market or a complete historical hiring series.

## Source and future work

Implemented source: [Keejob](https://www.keejob.com/offres-emploi/). Public accessibility alone does not establish collection or reuse permission; source permissions remain to be clarified for ongoing deployment or redistribution.

Possible next milestones are intentionally separate from the implemented stack:

- Collection recovery and durable progress for interrupted batches.
- Cross-batch identity, historical observations, and deduplication.
- Job categories and skill extraction, with agreed analytical definitions.
- Scheduling, monitoring, deployment, and CI checks.
- Managed lakehouse tables when their requirements are established.
- Automated BI publication selection, dashboard exports, and integration verification.

Superset provides the BI website; there is no custom frontend or FastAPI service. PostgreSQL is used only for Superset metadata. Remote/cloud deployment, a scheduler, Airflow DAGs, Kafka streaming, Spark processing, a dbt project, a feature store, ML models, and Iceberg/Delta tables are not implemented. pandas, DuckDB SQL, and Superset are the current analysis interfaces.

## Validation

After separating the projects, the pipeline image built successfully and a small
container run completed discovery, collection, silver transformation, and gold
publication against MinIO: one listing page, 17 candidate URLs, five successful
collections, five silver rows, and all four gold datasets. DuckDB and Jupyter
were absent from the pipeline dependency set. Exploration configuration and
Python syntax were checked; its separate environment has not yet received an
end-to-end MinIO query test. This is not a comprehensive automated test suite.
