"""Configure Superset's metadata database using environment variables."""
from sqlalchemy import event
from sqlalchemy.engine import Engine,URL

from gold_connection import configure_gold_connection
event.listen(Engine, "connect", configure_gold_connection)
import os



SECRET_KEY = os.environ["SUPERSET_SECRET_KEY"]

SQLALCHEMY_DATABASE_URI = URL.create(
    drivername="postgresql+psycopg2",
    username=os.environ["POSTGRES_USER"],
    password=os.environ["POSTGRES_PASSWORD"],
    host="superset-db",
    port=5432,
    database=os.environ["POSTGRES_DB"],
).render_as_string(hide_password=False)

SQLALCHEMY_TRACK_MODIFICATIONS = False