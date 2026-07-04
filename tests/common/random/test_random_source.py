from qsdc.common.random.classical import ClassicalRandomSource


def test_classical_random_source_is_reproducible():
    left = ClassicalRandomSource(5)
    right = ClassicalRandomSource(5)

    assert left.name == "classical"
    assert left.shuffled(range(8)) == right.shuffled(range(8))
    assert left.choice(("q", "p")) == right.choice(("q", "p"))
    assert left.uniform(-2.0, 2.0) == right.uniform(-2.0, 2.0)
