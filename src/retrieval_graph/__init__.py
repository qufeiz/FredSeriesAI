"""LangGraph retrieval agent entrypoint.

Exports the deployed conversational graph used by the FastAPI server and App Runner image.
Document indexing via `index_graph` is currently unused; only the main `graph` is supported.
"""

from retrieval_graph.graph import graph

__all__ = ["graph"]
