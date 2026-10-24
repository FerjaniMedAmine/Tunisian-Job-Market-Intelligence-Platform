# Job market exploration

This independent Python project provides notebooks and helpers for reading JSON,
reading Parquet into pandas, and querying Parquet with DuckDB from MinIO.
It does not run the ETL pipeline.

From the repository root:

```bash
cd exploration
uv sync --locked
uv run jupyter lab
```

Select the Python environment in `exploration/.venv` when using another notebook
editor. Keep storage credentials in the repository-root `.env`; the connection
helper loads that file through python-dotenv. For notebooks running on the host,
use `MINIO_ENDPOINT=http://127.0.0.1:19000`. MinIO must be running.

Notebook imports:

```python
from jobmarket_exploration.storage.connection import create_client, create_session
from jobmarket_exploration.storage.s3 import read_json, read_parquet
from jobmarket_exploration.storage.query import query_parquet
```

Object keys are relative to the bucket configured by `MINIO_BUCKET`.
DuckDB's first SQL query may need internet access to install its `httpfs`
extension. The notebooks currently have no cells; add exploration incrementally.
