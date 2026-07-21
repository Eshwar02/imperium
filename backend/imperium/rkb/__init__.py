"""Repository Knowledge Base (TDD §5, §6).

Persistent organizational knowledge instead of agent memory. Four stores:
  - store    : Postgres (relational) — structured facts, decision log, test history
  - embeddings: Qdrant — semantic context for RAG (TDD §6 memory hierarchy)
  - graph    : Neo4j — architecture / call / dependency knowledge graph
  - cache    : Redis — hot context, run coordination
"""
