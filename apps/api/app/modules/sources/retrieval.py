"""Source retrieval boundary.

The first source ingestion release uses the shared note retrieval result contract;
this module exists so later semantic/source synchronization logic stays modular.
"""

from app.modules.notes.retrieval import retrieve_external_chunks

__all__ = ["retrieve_external_chunks"]
