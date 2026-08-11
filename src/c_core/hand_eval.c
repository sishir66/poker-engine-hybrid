/*
 * 7-card hand evaluator. Direct port of src/engine/hand.py's Hand class --
 * same branching order, same tiebreak extraction, same wheel rule -- not a
 * reimplementation. See PokerEngine_Blueprint.md Phase IV design doc for
 * why this exists (calculate_win_odds()'s Monte Carlo loop only).
 *
 * evaluate_seven() returns a FIXED 6-int array, zero-padded past whatever
 * length get_hand_key() would naturally return for that hand's category.
 * Safe to compare against other evaluate_seven() output; NOT safe to
 * compare against get_hand_key()'s raw (variable-length) tuple without
 * truncating first -- see src/engine/c_hand_eval.py.
 */
#include <string.h>

/* All 21 five-index combinations out of 7 indices (0..6). */
static const int COMBOS[21][5] = {
    {0,1,2,3,4},{0,1,2,3,5},{0,1,2,3,6},{0,1,2,4,5},{0,1,2,4,6},
    {0,1,2,5,6},{0,1,3,4,5},{0,1,3,4,6},{0,1,3,5,6},{0,1,4,5,6},
    {0,2,3,4,5},{0,2,3,4,6},{0,2,3,5,6},{0,2,4,5,6},{0,3,4,5,6},
    {1,2,3,4,5},{1,2,3,4,6},{1,2,3,5,6},{1,2,4,5,6},{1,3,4,5,6},
    {2,3,4,5,6}
};

/* Evaluates exactly 5 cards into a fixed 6-int tiebreak array. */
static void evaluate_five(const int r[5], const int s[5], int out[6]) {
    int count[15] = {0};
    for (int i = 0; i < 5; i++) count[r[i]]++;

    int is_flush = 1;
    for (int i = 1; i < 5; i++) if (s[i] != s[0]) { is_flush = 0; break; }

    int sorted_ranks[5];
    memcpy(sorted_ranks, r, sizeof(sorted_ranks));
    for (int i = 1; i < 5; i++) {
        int key = sorted_ranks[i], j = i - 1;
        while (j >= 0 && sorted_ranks[j] > key) { sorted_ranks[j + 1] = sorted_ranks[j]; j--; }
        sorted_ranks[j + 1] = key;
    }

    int distinct = 1;
    for (int i = 1; i < 5; i++) if (sorted_ranks[i] != sorted_ranks[i - 1]) distinct++;

    /* Wheel: A-2-3-4-5, represented as high=5 (not 14) -- matches
     * get_hand_key()'s explicit wheel exception for straight/straight flush. */
    int is_wheel = (distinct == 5 && count[14] && count[2] && count[3] && count[4] && count[5]);

    int is_straight = 0, straight_high = 0;
    if (distinct == 5) {
        if (sorted_ranks[4] - sorted_ranks[0] == 4) { is_straight = 1; straight_high = sorted_ranks[4]; }
        else if (is_wheel) { is_straight = 1; straight_high = 5; }
    }

    /* dist: sorted-descending counts of the ranks actually present (mirrors
     * Python's sorted(Counter(...).values(), reverse=True)). */
    int dist[5], dn = 0;
    for (int rk = 2; rk <= 14; rk++) if (count[rk] > 0) dist[dn++] = count[rk];
    for (int i = 1; i < dn; i++) {
        int key = dist[i], j = i - 1;
        while (j >= 0 && dist[j] < key) { dist[j + 1] = dist[j]; j--; }
        dist[j + 1] = key;
    }

    /* Same if/elif order as Hand.get_rank_value() -- order matters, these
     * checks are not independently exclusive without it. */
    int rv;
    if (is_flush && is_straight) {
        /* Royal flush iff [lowest, highest] == [10, 14]. A non-wheel
         * straight's high is only ever 14 for the unique run 10-J-Q-K-A
         * (wheel already claims high=5 for any other ace-involving
         * straight), so straight_high==14 is equivalent and cheaper --
         * asserted by the royal-flush differential test, not assumed. */
        rv = (straight_high == 14) ? 9 : 8;
    }
    else if (dn == 2 && dist[0] == 4) rv = 7;   /* four of a kind: [4,1] */
    else if (dn == 2 && dist[0] == 3) rv = 6;   /* full house: [3,2] */
    else if (is_flush) rv = 5;
    else if (is_straight) rv = 4;
    else if (dn == 3 && dist[0] == 3) rv = 3;   /* three of a kind: [3,1,1] */
    else if (dn == 3 && dist[0] == 2) rv = 2;   /* two pair: [2,2,1] */
    else if (dn == 4) rv = 1;                    /* one pair: [2,1,1,1] */
    else rv = 0;                                  /* high card: [1,1,1,1,1] */

    for (int i = 0; i < 6; i++) out[i] = 0;
    out[0] = rv;

    if (rv == 0 || rv == 5) {
        /* High card / flush: all 5 ranks, descending. */
        for (int i = 0; i < 5; i++) out[1 + i] = sorted_ranks[4 - i];
    } else if (rv == 1) {
        int pair_r = 0;
        for (int rk = 14; rk >= 2; rk--) if (count[rk] == 2) { pair_r = rk; break; }
        out[1] = pair_r;
        int idx = 2;
        for (int rk = 14; rk >= 2; rk--) if (count[rk] == 1) out[idx++] = rk;
    } else if (rv == 2) {
        int idx = 1;
        for (int rk = 14; rk >= 2; rk--) if (count[rk] == 2) out[idx++] = rk;
        for (int rk = 14; rk >= 2; rk--) if (count[rk] == 1) { out[3] = rk; break; }
    } else if (rv == 3) {
        int trips_r = 0;
        for (int rk = 14; rk >= 2; rk--) if (count[rk] == 3) { trips_r = rk; break; }
        out[1] = trips_r;
        int idx = 2;
        for (int rk = 14; rk >= 2; rk--) if (count[rk] == 1) out[idx++] = rk;
    } else if (rv == 4 || rv == 8) {
        out[1] = straight_high;
    } else if (rv == 6) {
        for (int rk = 14; rk >= 2; rk--) if (count[rk] == 3) { out[1] = rk; break; }
        for (int rk = 14; rk >= 2; rk--) if (count[rk] == 2) { out[2] = rk; break; }
    } else if (rv == 7) {
        for (int rk = 14; rk >= 2; rk--) if (count[rk] == 4) { out[1] = rk; break; }
        for (int rk = 14; rk >= 2; rk--) if (count[rk] == 1) { out[2] = rk; break; }
    } else {
        /* rv == 9 */
        out[1] = 14;
    }
}

void evaluate_seven(const int* ranks, const int* suits, int* out) {
    int best[6];
    int have_best = 0;

    for (int c = 0; c < 21; c++) {
        int r5[5], s5[5];
        for (int i = 0; i < 5; i++) {
            r5[i] = ranks[COMBOS[c][i]];
            s5[i] = suits[COMBOS[c][i]];
        }
        int cur[6];
        evaluate_five(r5, s5, cur);

        if (!have_best) {
            memcpy(best, cur, sizeof(best));
            have_best = 1;
        } else {
            for (int i = 0; i < 6; i++) {
                if (cur[i] != best[i]) {
                    if (cur[i] > best[i]) memcpy(best, cur, sizeof(best));
                    break;
                }
            }
        }
    }

    memcpy(out, best, sizeof(best));
}
