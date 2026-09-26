"""Re-exports for the DB layer's public surface used outside `repositories/`."""

from app.db.session import check_connection

__all__ = ["check_connection"]
