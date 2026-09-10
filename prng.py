import random


def build_permutation(seed: bytes, slot_count: int) -> list[int]:
    rng = random.Random(seed)
    permutation = list(range(slot_count))
    rng.shuffle(permutation)
    return permutation


def pick_slots(seed: bytes, slot_count: int, needed: int) -> list[int]:
    permutation = build_permutation(seed, slot_count)
    return permutation[:needed]


def demo() -> None:
    slot_count = 12
    seed_a = bytes(range(32))
    seed_b = bytes(range(31, -1, -1))

    order_a = build_permutation(seed_a, slot_count)
    order_b = build_permutation(seed_a, slot_count)
    order_c = build_permutation(seed_b, slot_count)

    print(f"seed A run 1: {order_a}")
    print(f"seed A run 2: {order_b}   (same seed -> same order: {order_a == order_b})")
    print(f"seed B run 1: {order_c}   (different seed -> different order)")

    picked = pick_slots(seed_a, slot_count, 6)
    print(f"first 6 slots to embed (seed A): {picked}")

    occupied = [0] * slot_count
    for slot in picked:
        occupied[slot] = 1
    print(f"visual      : {occupied}   <- bits scattered, not sequential")


if __name__ == "__main__":
    demo()
