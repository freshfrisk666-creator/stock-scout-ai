"""V1 placeholder for the future intelligence/news agent.

M1 + M2 intentionally do not depend on an LLM or paid news API. The interface
is kept explicit so a later intelligence layer can enrich, rather than replace,
the deterministic technical engine.
"""


def add_intelligence(technical):
    return technical.copy()
