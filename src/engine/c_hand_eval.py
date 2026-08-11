"""
ctypes binding for src/c_core/hand_eval.c, plus a pure-Python fallback.

evaluate_seven() returns a FIXED 6-tuple (zero-padded), not get_hand_key()'s
variable-length one. Safe to compare against other evaluate_seven() output;
NOT safe to compare against get_hand_key()'s raw output (e.g. from
get_best_hand()) without truncating first -- see evaluate_seven_c()'s
docstring. This module and get_best_hand() intentionally return
differently-shaped keys; don't unify them without updating both call sites.
"""
import ctypes
import itertools
import os

from src.engine.hand import Hand

_LIB_PATH = os.path.join(os.path.dirname(__file__), '..', 'c_core', 'libhand_eval.so')

try:
    _lib = ctypes.CDLL(os.path.abspath(_LIB_PATH))
    _lib.evaluate_seven.argtypes = [
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_int),
    ]
    _lib.evaluate_seven.restype = None
    AVAILABLE = True
except OSError:
    _lib = None
    AVAILABLE = False


def evaluate_seven_c(cards):
    """Requires AVAILABLE. Returns a FIXED 6-tuple, zero-padded past
    get_hand_key()'s natural length for that hand's category.

    Safe to compare (==, <, >, sorted, max) against other evaluate_seven()
    output -- both sides pad identically, so ordering and equality both
    behave exactly as they would on the unpadded tuples.

    NOT safe to compare against get_hand_key()'s raw output directly (e.g.
    from get_best_hand(), which Stage 1's Showdown component uses per the
    Phase IV design doc, not this function). Python tuple equality requires
    matching length: (6, 10, 8) == (6, 10, 8, 0, 0, 0) is False even though
    they represent the identical hand. Truncate this function's output to
    len(get_hand_key()'s tuple) -- i.e. to the real tiebreak length for that
    rank_value -- before comparing across the two evaluators. The
    differential test does exactly this; any future code bridging the two
    evaluators must too."""
    ranks = (ctypes.c_int * 7)(*(c.rank for c in cards))
    suits = (ctypes.c_int * 7)(*(c.suit for c in cards))
    out = (ctypes.c_int * 6)()
    _lib.evaluate_seven(ranks, suits, out)
    return tuple(out)


def evaluate_seven_py(cards):
    """Pure-Python fallback -- identical to calculate_win_odds()'s pre-Stage-0.5
    evaluation, used when the C library hasn't been built."""
    return max(Hand(list(c)).get_hand_key() for c in itertools.combinations(cards, 5))


def evaluate_seven(cards):
    return evaluate_seven_c(cards) if AVAILABLE else evaluate_seven_py(cards)
