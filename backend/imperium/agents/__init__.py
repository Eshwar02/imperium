"""Multi-Agent Architecture (TDD §8, PRD §8).

Orchestrator (core/orchestrator.py) sequences these sub-agents and enforces the
approval gates. Each agent module implements its TDD responsibility, delegating to
the intelligence/ analyzers and the LLM routing chain.
"""
