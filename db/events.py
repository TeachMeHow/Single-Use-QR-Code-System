from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Protocol

from db.connection import create_connection, DB_PATH

TIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


def utc_now_str() -> str:
    return datetime.now(timezone.utc).strftime(TIME_FORMAT)


@dataclass(slots=True, frozen=True)
class SyncEvent:
    event_id: str
    origin_device_id: str
    event_type: str
    payload_json: str
    created_at: str

    @classmethod
    def create(
        cls,
        *,
        event_id: str,
        origin_device_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> "SyncEvent":
        return cls(
            event_id=event_id,
            origin_device_id=origin_device_id,
            event_type=event_type,
            payload_json=json.dumps(payload, separators=(",", ":"), sort_keys=True),
            created_at=utc_now_str(),
        )

    @property
    def payload(self) -> dict[str, Any]:
        return json.loads(self.payload_json)


class AbstractConnection(Protocol):
    def get_unsynced_peers(self) -> Iterable[str]:
        ...

    def send_event(self, peer_id: str, event: SyncEvent) -> bool:
        ...


def create_sync_tables(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sync_events (
            event_id TEXT PRIMARY KEY,
            origin_device_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sync_event_delivery (
            event_id TEXT NOT NULL,
            peer_id TEXT NOT NULL,
            synced INTEGER NOT NULL DEFAULT 0 CHECK (synced IN (0, 1)),
            last_attempt_at TEXT,
            synced_at TEXT,
            PRIMARY KEY (event_id, peer_id),
            FOREIGN KEY (event_id) REFERENCES sync_events(event_id)
        )
        """
    )

    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_sync_delivery_peer_synced
        ON sync_event_delivery(peer_id, synced)
        """
    )

    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_sync_events_created_at
        ON sync_events(created_at)
        """
    )


def row_to_sync_event(row: sqlite3.Row) -> SyncEvent:
    return SyncEvent(
        event_id=row["event_id"],
        origin_device_id=row["origin_device_id"],
        event_type=row["event_type"],
        payload_json=row["payload_json"],
        created_at=row["created_at"],
    )


def insert_event(conn: sqlite3.Connection, event: SyncEvent) -> None:
    conn.execute(
        """
        INSERT INTO sync_events (
            event_id,
            origin_device_id,
            event_type,
            payload_json,
            created_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            event.event_id,
            event.origin_device_id,
            event.event_type,
            event.payload_json,
            event.created_at,
        ),
    )


def mark_event_pending_for_peer(
    conn: sqlite3.Connection,
    event_id: str,
    peer_id: str,
) -> None:
    conn.execute(
        """
        INSERT INTO sync_event_delivery (
            event_id,
            peer_id,
            synced,
            last_attempt_at,
            synced_at
        )
        VALUES (?, ?, 0, NULL, NULL)
        ON CONFLICT(event_id, peer_id) DO NOTHING
        """,
        (event_id, peer_id),
    )


def mark_event_attempted(
    conn: sqlite3.Connection,
    event_id: str,
    peer_id: str,
) -> None:
    conn.execute(
        """
        UPDATE sync_event_delivery
        SET last_attempt_at = ?
        WHERE event_id = ? AND peer_id = ?
        """,
        (utc_now_str(), event_id, peer_id),
    )


def mark_event_synced(
    conn: sqlite3.Connection,
    event_id: str,
    peer_id: str,
) -> None:
    now = utc_now_str()
    conn.execute(
        """
        UPDATE sync_event_delivery
        SET synced = 1,
            last_attempt_at = ?,
            synced_at = ?
        WHERE event_id = ? AND peer_id = ?
        """,
        (now, now, event_id, peer_id),
    )


def get_unsynced_event_ids_for_peer(
    conn: sqlite3.Connection,
    peer_id: str,
) -> list[str]:
    rows = conn.execute(
        """
        SELECT event_id
        FROM sync_event_delivery
        WHERE peer_id = ? AND synced = 0
        ORDER BY event_id
        """,
        (peer_id,),
    ).fetchall()

    return [row["event_id"] for row in rows]


def get_event_by_id(conn: sqlite3.Connection, event_id: str) -> SyncEvent | None:
    row = conn.execute(
        """
        SELECT event_id, origin_device_id, event_type, payload_json, created_at
        FROM sync_events
        WHERE event_id = ?
        """,
        (event_id,),
    ).fetchone()

    if row is None:
        return None

    return row_to_sync_event(row)


def store_event_and_seed_unsynced_devices(
    conn: sqlite3.Connection,
    connection: AbstractConnection,
    event: SyncEvent,
) -> None:
    insert_event(conn, event)

    unsynced_peers = list(connection.get_unsynced_peers())
    if not unsynced_peers:
        return

    for peer_id in unsynced_peers:
        mark_event_pending_for_peer(conn, event.event_id, peer_id)

        mark_event_attempted(conn, event.event_id, peer_id)
        sent = connection.send_event(peer_id, event)

        if sent:
            mark_event_synced(conn, event.event_id, peer_id)


def flush_unsynced_events(
    conn: sqlite3.Connection,
    connection: AbstractConnection,
) -> None:
    for peer_id in connection.get_unsynced_peers():
        event_ids = get_unsynced_event_ids_for_peer(conn, peer_id)

        for event_id in event_ids:
            event = get_event_by_id(conn, event_id)
            if event is None:
                continue

            mark_event_attempted(conn, event.event_id, peer_id)
            sent = connection.send_event(peer_id, event)

            if sent:
                mark_event_synced(conn, event.event_id, peer_id)


class DummyConnection:
    def __init__(self, reachable_unsynced_peers: list[str]) -> None:
        self._peers = reachable_unsynced_peers

    def get_unsynced_peers(self) -> Iterable[str]:
        return self._peers

    def send_event(self, peer_id: str, event: SyncEvent) -> bool:
        print(f"SEND -> peer={peer_id} event_id={event.event_id} type={event.event_type}")
        return True


if __name__ == "__main__":
    conn = create_connection(DB_PATH)
    create_sync_tables(conn)
    conn.commit()

    connection = DummyConnection(
        reachable_unsynced_peers=["device-b", "device-c"]
    )

    event = SyncEvent.create(
        event_id="device-a:000001",
        origin_device_id="device-a",
        event_type="code_invalidated",
        payload={"code_id": "7KMQ8A-20260307-154522-S0042"},
    )

    with conn:
        store_event_and_seed_unsynced_devices(conn, connection, event)

    flush_unsynced_events(conn, connection)

    conn.close()
