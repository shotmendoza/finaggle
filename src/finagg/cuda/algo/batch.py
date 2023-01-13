"""Definitions related to batches of data passed between algorithm modules."""

from enum import Enum


class Batch(str, Enum):
    """Typical batch elements for convenience.

    Prefer to use this enumeration over strings just to keep batch element
    access consistent across modules.

    """

    #: Key denoting observations from the environment.
    #: Typically processed by a policy model.
    OBS = "obs"

    #: Key denoting features output from a policy model.
    #: Typically processed by a policy action distribution.
    FEATURES = "features"

    #: Key denoting features output by a policy action distribution.
    #: Usually propagated through an environment.
    ACTIONS = "actions"

    #: Key denoting the log probability of taking `actions` with feature
    #: and a model. Typically used by learning algorithms.
    LOGP = "logp"

    #: Key denoting value function approximation from a policy model.
    #: Typically used by learning algorithms or for analyzing a trained model.
    VALUES = "values"
