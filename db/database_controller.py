
from db.connection import create_connection
from db.code_database import create_table
from pathlib import Path


class DatabaseController:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = None

    def open_database(self) -> None:
        self.conn = create_connection(self.db_path)
        create_table(self.conn)
        self.conn.commit()

    def drop_database(self) -> None:
        if self.conn is not None:
            self.conn.close()
            self.conn = None
        if self.db_path.exists():
            self.db_path.unlink()


if __name__ == "__main__":
    db_path = Path.cwd() / "access_codes.db"
    c = DatabaseController(db_path=db_path)
    c.drop_database()
