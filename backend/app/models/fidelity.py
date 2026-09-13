"""Pure-Python narration fidelity: word error rate between a script and a transcript."""

import re

_TOKEN = re.compile(r"[a-z0-9']+")


def normalise_words(text: str) -> list[str]:
    return _TOKEN.findall(text.lower().replace("’", "'"))


def word_error_rate(reference: str, hypothesis: str) -> float:
    """Levenshtein distance over words divided by the reference length (0 = identical)."""
    ref, hyp = normalise_words(reference), normalise_words(hypothesis)
    if not ref:
        return 0.0 if not hyp else 1.0
    previous = list(range(len(hyp) + 1))
    for i, word in enumerate(ref, start=1):
        current = [i]
        for j, other in enumerate(hyp, start=1):
            current.append(
                min(
                    previous[j] + 1,
                    current[j - 1] + 1,
                    previous[j - 1] + (word != other),
                )
            )
        previous = current
    return min(previous[-1] / len(ref), 1.0)


def fidelity(reference: str, hypothesis: str) -> float:
    return 1.0 - word_error_rate(reference, hypothesis)
