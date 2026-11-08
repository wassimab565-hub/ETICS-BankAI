import re

from ai_engine.chunking.chunker import Chunk

MIN_SIGNALS = 2  # distinct signals a chunk needs to be sent to the model

RISK_SIGNALS = {
    "termination": r"r[ée]sili|cl[ôo]tur|fermeture|terminat",
    "notice": r"pr[ée]avis|notice period|without notice",
    "change": r"modifi|unilat[ée]ral|[àa] notre initiative|[àa] tout moment|at any time|amend",
    "suspension": r"suspen|bloqu|restreindre|restrict",
    "liability": r"responsabilit|ne saurait [êe]tre tenu|d[ée]clin|liabilit",
    "data": r"donn[ée]es personnelles|rgpd|cnil|partenaires|prospection|personal data|third part",
    "penalty": r"p[ée]nalit|indemnit|int[ée]r[êe]ts de retard|d[ée]bit[ée]e? d.office|penalt",
    "obligation": r"vous vous engagez|le client est tenu|vous [êe]tes tenu|obligation|you agree|you must",
    "vulnerability": r"mineur|tutelle|curatelle|sauvegarde de justice|fragil|vulnerab",
    "discrimination": r"discrimin|nationalit",
}
_COMPILED = {name: re.compile(pattern, re.IGNORECASE) for name, pattern in RISK_SIGNALS.items()}


def risk_signals(text: str) -> set[str]:
    """Names of the distinct risk signals found in a text."""
    return {name for name, pattern in _COMPILED.items() if pattern.search(text)}


def select_risk_chunks(chunks: list[Chunk], min_signals: int = MIN_SIGNALS) -> list[int]:
    """Indexes of the chunks worth sending to the risk analysis (document order)."""
    return [c.index for c in chunks if len(risk_signals(c.text)) >= min_signals]