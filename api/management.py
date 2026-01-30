"""
Core business logic for issuing, validating, and revoking management codes.
"""

from __future__ import annotations

import secrets
import string
from typing import Optional

from api.database import get_connection, init_db
from api.security import fingerprint, hash_code, verify_code

ALLOWED_CHARS = string.ascii_letters + string.digits + "-"
MIN_LENGTH = 8
MAX_LENGTH = 16


class ManagementCodeError(Exception):
    """Base class for management code errors."""


class PermissionDenied(ManagementCodeError):
    """Raised when the caller does not have permission."""


class InvalidCode(ManagementCodeError):
    """Raised when a provided code is invalid or inactive."""


class ManagementCodeService:
    """Service layer for management code operations."""

    def __init__(self) -> None:
        init_db()

    def initialize_master(self, code: str) -> dict:
        """
        Insert the first master_admin code when none exist.
        Raises an error if a master_admin already exists.
        """
        self._assert_format(code)
        with get_connection() as conn:
            existing = conn.execute(
                "SELECT COUNT(*) FROM management_codes WHERE role = 'master_admin'"
            ).fetchone()[0]
            if existing:
                raise ManagementCodeError("Master admin code already exists.")
            record = self._store_code(conn, code, role="master_admin", created_by=None)
            return record

    def issue_admin_code(self, issuer_code: str) -> dict:
        """Issue a new admin code after validating the issuer as master_admin."""
        issuer = self._validate_active_code(issuer_code, required_role="master_admin")
        new_code = self._generate_unique_code()
        with get_connection() as conn:
            record = self._store_code(conn, new_code, role="admin", created_by=issuer["id"])
        record["plain_code"] = new_code
        return record

    def deactivate_code(self, actor_code: str, target_code: str) -> dict:
        """
        Deactivate a target code. Only a master_admin (actor) may perform this action.
        """
        self._validate_active_code(actor_code, required_role="master_admin")
        target = self._validate_active_code(target_code)
        with get_connection() as conn:
            conn.execute(
                "UPDATE management_codes SET is_active = 0 WHERE id = ?", (target["id"],)
            )
        target["is_active"] = 0
        return target

    def validate_code(self, code: str) -> dict:
        """Validate any active code and return its metadata."""
        return self._validate_active_code(code)

    def _generate_unique_code(self) -> str:
        """Generate a unique code that fits the 8-16 length requirement."""
        length = secrets.choice(range(MIN_LENGTH, MAX_LENGTH + 1))
        while True:
            candidate = "".join(secrets.choice(ALLOWED_CHARS) for _ in range(length))
            try:
                self._assert_format(candidate)
            except ManagementCodeError:
                continue
            fp = fingerprint(candidate)
            with get_connection() as conn:
                row = conn.execute(
                    "SELECT 1 FROM management_codes WHERE code_fingerprint = ?", (fp,)
                ).fetchone()
            if row is None:
                return candidate

    def _validate_active_code(self, code: str, required_role: Optional[str] = None) -> dict:
        """
        Ensure the code exists, is active, and optionally matches the required role.
        Raises InvalidCode or PermissionDenied upon failure.
        """
        self._assert_format(code)
        fp = fingerprint(code)
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM management_codes WHERE code_fingerprint = ?", (fp,)
            ).fetchone()

        if row is None or not verify_code(code, row["code_salt"], row["code_hash"]):
            raise InvalidCode("Code is not recognized.")
        if not row["is_active"]:
            raise InvalidCode("Code is inactive.")
        if required_role and row["role"] != required_role:
            raise PermissionDenied("Insufficient role.")
        return dict(row)

    def _store_code(
        self, conn, code: str, role: str, created_by: Optional[int]
    ) -> dict:
        """Persist a newly generated code."""
        fp = fingerprint(code)
        salt, hashed = hash_code(code)
        cur = conn.execute(
            """
            INSERT INTO management_codes (
                code_hash, code_salt, code_fingerprint, role, created_by, is_active
            ) VALUES (?, ?, ?, ?, ?, 1)
            """,
            (hashed, salt, fp, role, created_by),
        )
        conn.commit()
        record = conn.execute(
            "SELECT * FROM management_codes WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
        return dict(record)

    def _assert_format(self, code: str) -> None:
        """Ensure the code follows length/character constraints."""
        if not (MIN_LENGTH <= len(code) <= MAX_LENGTH):
            raise ManagementCodeError("Code must be 8-16 characters.")
        invalid = [c for c in code if c not in ALLOWED_CHARS]
        if invalid:
            raise ManagementCodeError("Code must be alphanumeric or hyphen.")
        if not any(c.isalpha() for c in code) or not any(c.isdigit() for c in code):
            raise ManagementCodeError("Code must include both letters and digits.")
