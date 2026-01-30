"""
Data cache node helpers for obfuscated child/date state storage.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import threading
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence

INTERNAL_STATES: Sequence[str] = (
    "00",
    "01",
    "10",
    "11",
    "*0",
    "0*",
    "*1",
    "1*",
    "__",
    "_",
)

ASCII_LETTERS = [*list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"), *list("abcdefghijklmnopqrstuvwxyz")]
THAI_LETTERS = [chr(code) for code in range(0x0E01, 0x0E2F)]
ARABIC_LETTERS = [
    *[chr(code) for code in range(0x0621, 0x063B)],
    *[chr(code) for code in range(0x0641, 0x064B)],
]
UNICODE_ALLOWED = ASCII_LETTERS + THAI_LETTERS + ARABIC_LETTERS


def _base64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _base64std(data: bytes) -> str:
    return base64.b64encode(data).decode("utf-8")


def node_key_raw(secret: str, child_id: str, yyyymmdd: str) -> bytes:
    message = f"{child_id}|{yyyymmdd}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).digest()


def node_lookup_key(secret: str, child_id: str, yyyymmdd: str) -> str:
    return _base64url(node_key_raw(secret, child_id, yyyymmdd))


def node_key_encoded(secret: str, child_id: str, yyyymmdd: str) -> str:
    return _base64std(node_key_raw(secret, child_id, yyyymmdd))


def prefix12(lookup_key: str) -> str:
    return lookup_key[:12]


def _build_unicode_pools() -> Dict[str, List[str]]:
    rng = secrets.SystemRandom()
    shuffled = UNICODE_ALLOWED.copy()
    rng.shuffle(shuffled)
    pools: Dict[str, List[str]] = {state: [] for state in INTERNAL_STATES}
    for index, char in enumerate(shuffled):
        pools[INTERNAL_STATES[index % len(INTERNAL_STATES)]].append(char)
    return pools


UNICODE_POOLS = _build_unicode_pools()
UNICODE_TO_STATE = {
    char: state for state, chars in UNICODE_POOLS.items() for char in chars
}


def encode_states(states: Iterable[str]) -> str:
    rng = secrets.SystemRandom()
    chars: List[str] = []
    for state in states:
        pool = UNICODE_POOLS[state]
        chars.append(rng.choice(pool))
    return "".join(chars)


def decode_states(token: str) -> List[str]:
    return [UNICODE_TO_STATE[char] for char in token]


def generate_dictionary() -> Dict[str, str]:
    states = list(INTERNAL_STATES)
    secrets.SystemRandom().shuffle(states)
    return {str(index): state for index, state in enumerate(states)}


@dataclass(frozen=True)
class DictionaryRecord:
    dict_id: str
    mapping: Dict[str, str]


class DictionaryRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: Dict[str, DictionaryRecord] = {}

    def create(self) -> DictionaryRecord:
        record = DictionaryRecord(dict_id=secrets.token_urlsafe(16), mapping=generate_dictionary())
        with self._lock:
            self._records[record.dict_id] = record
        return record

    def get(self, dict_id: str) -> DictionaryRecord | None:
        with self._lock:
            return self._records.get(dict_id)


def _normalize_events(events: Sequence[Dict[str, object]]) -> str:
    serialized = [json.dumps(event, sort_keys=True, separators=(",", ":")) for event in events]
    serialized.sort()
    return "[" + ",".join(serialized) + "]"


def _digit_stream(seed: bytes) -> Iterable[int]:
    counter = 0
    while True:
        digest = hashlib.sha256(seed + counter.to_bytes(4, "big")).digest()
        for byte in digest:
            yield byte % 10
        counter += 1


def build_state_token(events: Sequence[Dict[str, object]], mapping: Dict[str, str], length: int = 64) -> str:
    normalized = _normalize_events(events).encode("utf-8")
    seed = hashlib.sha256(normalized).digest()
    digits = _digit_stream(seed)
    states = [mapping[str(next(digits))] for _ in range(length)]
    return encode_states(states)


def build_node(
    *,
    secret: str,
    child_id: str,
    yyyymmdd: str,
    events: Sequence[Dict[str, object]],
    registry: DictionaryRegistry,
) -> Dict[str, object]:
    record = registry.create()
    lookup_key = node_lookup_key(secret, child_id, yyyymmdd)
    return {
        "v": 1,
        "node_key": node_key_encoded(secret, child_id, yyyymmdd),
        "prefix12": prefix12(lookup_key),
        "date": yyyymmdd,
        "state_token": build_state_token(events, record.mapping),
        "dict_id": record.dict_id,
        "events": list(events),
        "derived": {},
    }


class NodeAccessBlocked(Exception):
    """Raised when node access should be blocked without decoding."""


def enforce_node_access(dict_id: str | None, allowed_zone: bool, registry: DictionaryRegistry) -> None:
    if not dict_id or not registry.get(dict_id):
        raise NodeAccessBlocked("Missing dict_id")
    if not allowed_zone:
        raise NodeAccessBlocked("Access blocked")
