"""reject_reasoning: catches leaked chain-of-thought without flagging narration."""

import pytest

from app.schemas import reject_reasoning


@pytest.mark.parametrize(
    "text",
    [
        "<think>I should outline the claims first</think>",
        "Okay, let me think about how to phrase this.",
        "So, I need to cover the three claims in order.",
        "First, I will summarize the source excerpt.",
        "The user provided a request about coffee brewing.",
    ],
)
def test_reject_reasoning_rejects_leaked_thought(text):
    with pytest.raises(ValueError, match="contains model reasoning"):
        reject_reasoning(text)


@pytest.mark.parametrize(
    "text",
    [
        "So, let's wrap this up with one final tip on the best way to brew your coffee.",
        "Alright, let's dive into how espresso extraction actually works.",
        "Let's take a look at what happens inside the portafilter.",
    ],
)
def test_reject_reasoning_allows_narrator_openers(text):
    assert reject_reasoning(text) == text
