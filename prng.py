import hashlib
import random


def derive_seed(passphrase: str) -> int:
    return int.from_bytes(hashlib.sha256(passphrase.encode("utf-8")).digest(), "big")


def build_permutation(seed: int, slot_count: int) -> list[int]:
    rng = random.Random(seed)
    permutation = list(range(slot_count))
    rng.shuffle(permutation)
    return permutation


def pick_slots(seed: int, slot_count: int, needed: int) -> list[int]:
    permutation = build_permutation(seed, slot_count)
    return permutation[:needed]


def demo() -> None:
    slot_count = 12
    seed_a = derive_seed("correct horse battery staple")
    seed_b = derive_seed("a different passphrase")

    order_a = build_permutation(seed_a, slot_count)
    order_b = build_permutation(seed_a, slot_count)
    order_c = build_permutation(seed_b, slot_count)

    print(f"seed A run 1: {order_a}")
    print(f"seed A run 2: {order_b}   (same pass -> same order: {order_a == order_b})")
    print(f"seed B run 1: {order_c}   (different pass -> different order)")

    picked = pick_slots(seed_a, slot_count, 6)
    occupied = [0] * slot_count
    for slot in picked:
        occupied[slot] = 1
    print(f"first 6 slots : {picked}")
    print(f"visual        : {occupied}   <- bits scattered, not sequential")


if __name__ == "__main__":
    demo()
