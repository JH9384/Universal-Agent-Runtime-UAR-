import json
import sqlite3
import hashlib
import time
from .state import STORE
from .config import DB_PATH  # type: ignore


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def canonical_digest(payload):
    raw = json.dumps(payload, sort_keys=True).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def create_record(mediaType, mode, attributes, links, content):
    envelope = {
        "mediaType": mediaType,
        "mode": mode,
        "attributes": attributes,
        "links": links,
        "content": content,
    }
    digest = canonical_digest(envelope)
    record = {"digest": digest, "created_at": time.time(), **envelope}
    STORE[digest] = record
    return record
