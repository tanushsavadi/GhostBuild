"""Reusable presentation policy: human action first, exact identifiers in reference views.

The copy is authored/researched card data. This path never paraphrases a safety
instruction with a model, strips a value, or makes up a friendlier part name.
"""

from contracts.models import Cue, Step


def instruction(step: Step) -> Cue:
    return step.instruction or step.cue
