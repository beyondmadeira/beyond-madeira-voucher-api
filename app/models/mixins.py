from app.extensions import db
from datetime import datetime, timezone


class AirtableSyncMixin:
    airtable_id = db.Column(db.Text, unique=True, nullable=True, index=True)
    synced_at = db.Column(db.DateTime, nullable=True)
    dirty = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
