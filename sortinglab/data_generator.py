"""Fixed-seed integer datasets. No global random state is changed."""
import random

DISTRIBUTIONS = ("random", "sorted", "reversed", "nearly", "few_unique")
MAX_N = 1_000_000


def generate(n: int, distribution: str, seed: int = 42) -> list[int]:
    """Generate n integers; nearly uses floor(0.01*n) random pair swaps.

    Random is uniform over [-n,n]. Ordered inputs use distinct integers.
    Few-unique samples uniformly from 0..9 (not exactly ten for tiny n).
    """
    if isinstance(n, bool) or not isinstance(n, int) or not 0 <= n <= MAX_N:
        raise ValueError(f"n must be an integer in [0, {MAX_N}]")
    if distribution not in DISTRIBUTIONS:
        raise ValueError(f"Unknown distribution: {distribution}")
    rng = random.Random(seed)
    if distribution == "random":
        return [rng.randint(-n, n) for _ in range(n)]
    if distribution == "few_unique":
        return [rng.randrange(10) for _ in range(n)]
    a = list(range(n))
    if distribution == "reversed":
        a.reverse()
    elif distribution == "nearly" and n >= 2:
        for _ in range(n // 100):
            i, j = rng.sample(range(n), 2)
            a[i], a[j] = a[j], a[i]
    return a
