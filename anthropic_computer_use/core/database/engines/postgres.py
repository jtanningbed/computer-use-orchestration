from typing import Any, Optional, Tuple
import psycopg2
from ..engine import DatabaseEngine

class PostgresEngine(DatabaseEngine):
    """PostgreSQL database engine implementation"""
    
    def __init__(self, host: str, database: str, user: str, password: str):
        self.host = host
        self.database = database
        self.user = user
        self.password = password
        self.conn = None
        self.cursor = None

    def connect(self) -> None:
        try:
            self.conn = psycopg2.connect(
                host=self.host,
                database=self.database,
                user=self.user,
                password=self.password
            )
            self.cursor = self.conn.cursor()
        except Exception as e:
            raise ConnectionError(f"Failed to connect to PostgreSQL: {str(e)}")

    def disconnect(self) -> None:
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()

    def execute(self, query: str, params: Optional[Tuple] = None) -> Any:
        try:
            self.cursor.execute(query, params)
            self.conn.commit()
            return self.cursor
        except Exception as e:
            self.conn.rollback()
            raise Exception(f"Query execution failed: {str(e)}")

    def fetch_all(self, query: str, params: Optional[Tuple] = None) -> list[dict[str, Any]]:
        try:
            self.cursor.execute(query, params)
            columns = [desc[0] for desc in self.cursor.description]
            results = []
            for row in self.cursor.fetchall():
                results.append(dict(zip(columns, row)))
            return results
        except Exception as e:
            raise Exception(f"Failed to fetch results: {str(e)}")

    def fetch_one(self, query: str, params: Optional[Tuple] = None) -> Optional[dict[str, Any]]:
        try:
            self.cursor.execute(query, params)
            columns = [desc[0] for desc in self.cursor.description]
            row = self.cursor.fetchone()
            if row:
                return dict(zip(columns, row))
            return None
        except Exception as e:
            raise Exception(f"Failed to fetch result: {str(e)}")
