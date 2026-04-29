"""Utility for PostgreSQL connection and database bootstrap."""

import os
from dataclasses import dataclass

import psycopg2
from psycopg2.extensions import connection as PgConnection


@dataclass
class DBConfig:
    host: str = os.getenv("POSTGRES_HOST", "localhost")
    port: int = int(os.getenv("POSTGRES_PORT", "5432"))
    user: str = os.getenv("POSTGRES_USER", "docuser")
    password: str = os.getenv("POSTGRES_PASSWORD", "docpassword")
    maintenance_db: str = os.getenv("POSTGRES_MAINTENANCE_DB", "postgres")
    app_db: str = os.getenv("POSTGRES_DB", "docprocessing")


class DBInitializer:
    def __init__(self, config: DBConfig | None = None):
        self.config = config or DBConfig()

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
