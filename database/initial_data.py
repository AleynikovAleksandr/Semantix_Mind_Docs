"""Utility for PostgreSQL connection, database bootstrap, and schema setup."""

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import psycopg2
from psycopg2.extensions import connection as PgConnection

from app.config import settings


@dataclass
class DBConfig:
    host: str
    port: int
    user: str
    password: str
    maintenance_db: str
    app_db: str

    @classmethod
    def from_settings(cls) -> "DBConfig":
        parsed = urlparse(settings.sync_database_url)
        app_db = (parsed.path or "/docprocessing").lstrip("/") or "docprocessing"
        return cls(
            host=parsed.hostname or "localhost",
            port=parsed.port or 5432,
            user=parsed.username or "docuser",
            password=parsed.password or "docpassword",
            maintenance_db="postgres",
            app_db=app_db,
        )


class DBInitializer:
    def __init__(self, config: DBConfig | None = None):
        self.config = config or DBConfig.from_settings()

    def connect(self, db_name: str | None = None) -> PgConnection:
        """Метод 1: простое подключение к указанной БД."""
        return psycopg2.connect(
            host=self.config.host,
            port=self.config.port,
            user=self.config.user,
            password=self.config.password,
            dbname=db_name or self.config.app_db,
        )

    def create_database_and_switch(self) -> PgConnection:
        """Метод 2: создать БД (если нужно) и подключиться к ней."""
        maintenance_conn = self.connect(self.config.maintenance_db)
        maintenance_conn.autocommit = True

        with maintenance_conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s",
                (self.config.app_db,),
            )
            exists = cur.fetchone() is not None
            if not exists:
                cur.execute(f'CREATE DATABASE "{self.config.app_db}"')

        maintenance_conn.close()
        return self.connect(self.config.app_db)

    def apply_schema(self, conn: PgConnection, schema_path: Path | None = None) -> None:
        """Apply database/schema.sql so all tables exist on application startup."""
        schema_path = schema_path or Path(__file__).with_name("schema.sql")
        if not schema_path.exists():
            raise FileNotFoundError(f"Database schema file not found: {schema_path}")

        sql = schema_path.read_text(encoding="utf-8")
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()

    def initialize(self) -> None:
        """Create the application database if needed and apply the SQL schema."""
        conn = self.create_database_and_switch()
        try:
            self.apply_schema(conn)
        finally:
            conn.close()
