"""
Database utilities for the management code service.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

# SQLite database lives under data/ so it is easy to inspect/backup.
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("DB_PATH", str(BASE_DIR / "data" / "management_codes.db")))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def get_connection() -> sqlite3.Connection:
    """Return a SQLite connection with Row factory enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables when missing."""
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS management_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code_hash TEXT NOT NULL,
                code_salt TEXT NOT NULL,
                code_fingerprint TEXT NOT NULL UNIQUE,
                role TEXT NOT NULL,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY(created_by) REFERENCES management_codes(id)
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS link_issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                child_key TEXT NOT NULL,
                token_hash TEXT NOT NULL,
                token_salt TEXT NOT NULL,
                token_fingerprint TEXT NOT NULL UNIQUE,
                otp_hash TEXT NOT NULL,
                otp_salt TEXT NOT NULL,
                otp_fingerprint TEXT NOT NULL UNIQUE,
                issued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                used_at TIMESTAMP,
                revoked_at TIMESTAMP
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS child_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                child_key TEXT NOT NULL,
                line_user_id TEXT NOT NULL,
                linked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(child_key, line_user_id)
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS line_users (
                line_user_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                followed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS line_statement_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                statement_id TEXT NOT NULL,
                child_key TEXT NOT NULL,
                line_user_id TEXT NOT NULL,
                status TEXT NOT NULL,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS line_statement_replies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                statement_id TEXT NOT NULL,
                child_key TEXT,
                line_user_id TEXT NOT NULL,
                status TEXT NOT NULL,
                comment TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(statement_id, line_user_id)
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS line_event_responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL,
                child_key TEXT,
                line_user_id TEXT NOT NULL,
                status TEXT NOT NULL,
                responded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(event_id, line_user_id)
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS line_comment_requests (
                line_user_id TEXT PRIMARY KEY,
                statement_id TEXT NOT NULL,
                requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS line_message_deliveries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_type TEXT NOT NULL,
                child_key TEXT,
                line_user_id TEXT NOT NULL,
                status TEXT NOT NULL,
                payload TEXT,
                statement_id TEXT,
                event_id TEXT,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_identities (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                external_id TEXT NOT NULL,
                display_hint TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(provider, external_id),
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sms_challenges (
                id TEXT PRIMARY KEY,
                phone_e164 TEXT,
                phone_hash TEXT NOT NULL,
                code_hash TEXT NOT NULL,
                purpose TEXT NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                tries_left INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                consumed_at TIMESTAMP
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS login_management_settings (
                id TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL,
                updated_by_admin_id TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS children (
                id TEXT PRIMARY KEY,
                external_child_id TEXT,
                display_label TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_nodes (
                statement_id TEXT PRIMARY KEY,
                child_id TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS guardian_links (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                child_id TEXT NOT NULL,
                linked_via TEXT NOT NULL,
                valid_from DATE NOT NULL,
                valid_to DATE,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, child_id),
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS notification_threads (
                id TEXT PRIMARY KEY,
                child_id TEXT NOT NULL,
                status TEXT NOT NULL,
                created_by_staff_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS notification_messages (
                id TEXT PRIMARY KEY,
                thread_id TEXT NOT NULL,
                sender_type TEXT NOT NULL,
                sender_id TEXT NOT NULL,
                body_text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(thread_id) REFERENCES notification_threads(id)
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS notification_reads (
                id TEXT PRIMARY KEY,
                thread_id TEXT NOT NULL,
                reader_type TEXT NOT NULL,
                reader_id TEXT NOT NULL,
                last_read_at TIMESTAMP NOT NULL,
                UNIQUE(thread_id, reader_type, reader_id)
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS notify_qr_tokens (
                id TEXT PRIMARY KEY,
                thread_id TEXT NOT NULL,
                child_id TEXT NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                nonce TEXT NOT NULL,
                consumed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS qr_nonces (
                nonce TEXT PRIMARY KEY,
                statement_id TEXT NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS admin_users (
                id TEXT PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                must_change_password INTEGER NOT NULL DEFAULT 1,
                is_active INTEGER NOT NULL DEFAULT 1,
                failed_attempts INTEGER NOT NULL DEFAULT 0,
                lock_until TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS wifi_local_settings (
                id TEXT PRIMARY KEY,
                site_id TEXT,
                enabled INTEGER NOT NULL DEFAULT 0,
                ssid TEXT,
                local_api_base_url TEXT NOT NULL,
                local_api_port INTEGER,
                allowed_cidr_list TEXT NOT NULL,
                device_shared_secret_enc TEXT NOT NULL,
                heartbeat_interval_sec INTEGER NOT NULL,
                updated_by_admin_id TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(updated_by_admin_id) REFERENCES admin_users(id)
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS fastapi_settings (
                id TEXT PRIMARY KEY,
                enabled INTEGER NOT NULL DEFAULT 1,
                allowed_cidr_list TEXT NOT NULL,
                shared_token_enc TEXT NOT NULL,
                local_mode INTEGER NOT NULL DEFAULT 1,
                require_save_token INTEGER NOT NULL DEFAULT 1,
                require_sync_token INTEGER NOT NULL DEFAULT 1,
                require_latest_token INTEGER NOT NULL DEFAULT 0,
                updated_by_admin_id TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(updated_by_admin_id) REFERENCES admin_users(id)
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_html_assets (
                id TEXT PRIMARY KEY,
                app_key TEXT NOT NULL,
                app_name TEXT NOT NULL,
                filename TEXT NOT NULL,
                version_label TEXT NOT NULL,
                version_number INTEGER NOT NULL,
                storage_path TEXT NOT NULL,
                updated_by_admin_id TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                is_latest INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY(updated_by_admin_id) REFERENCES admin_users(id)
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS wifi_local_datasets (
                id TEXT PRIMARY KEY,
                version_label TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                updated_by TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS admin_audit_logs (
                id TEXT PRIMARY KEY,
                actor_admin_id TEXT NOT NULL,
                action TEXT NOT NULL,
                meta_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(actor_admin_id) REFERENCES admin_users(id)
            );
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_wifi_local_settings_site
            ON wifi_local_settings(site_id);
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_fastapi_settings_single
            ON fastapi_settings(id);
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_app_html_assets_key
            ON app_html_assets(app_key, is_latest);
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_link_issues_child_key
            ON link_issues(child_key);
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_raw_attendance_child_date
            ON raw_attendance_events(child_id, date);
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_daily_node_events_child_date
            ON daily_node_events(child_id, date);
            """
        )
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_daily_nodes_active
            ON daily_nodes(child_id, date)
            WHERE status = 'ACTIVE';
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_calc_history_node
            ON calc_history(daily_node_id);
            """
        )
        conn.execute(
            """
            CREATE VIEW IF NOT EXISTS view_active_daily_nodes AS
            SELECT * FROM daily_nodes WHERE status = 'ACTIVE';
            """
        )
        conn.execute(
            """
            CREATE VIEW IF NOT EXISTS view_daily_node_history AS
            SELECT
                dn.*,
                ch.payload AS calc_payload,
                ch.created_at AS calc_created_at
            FROM daily_nodes AS dn
            LEFT JOIN calc_history AS ch
                ON ch.daily_node_id = dn.id;
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_line_statement_child
            ON line_statement_messages(child_key, sent_at);
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_guardian_links_subject
            ON guardian_links(user_id, is_active);
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_notification_thread_child
            ON notification_threads(child_id);
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_notification_messages_thread
            ON notification_messages(thread_id, created_at);
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_notification_reads_thread
            ON notification_reads(thread_id);
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_daily_nodes_child
            ON daily_nodes(child_id);
            """
        )
