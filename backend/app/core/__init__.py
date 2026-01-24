"""
app/core/__init__.py
--------------------
Exposes core functionality like database management.
This allows imports like: `from app.core import init_db`
"""

from .database import init_db, save_message, get_history
