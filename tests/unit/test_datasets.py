from types import SimpleNamespace as NS

from src.core.datasets import parents_first


def test_parents_come_before_children_and_siblings_keep_order():
    child = NS(id=3, parent_id=2)
    grandchild = NS(id=4, parent_id=3)
    root_a = NS(id=2, parent_id=None)
    root_b = NS(id=1, parent_id=None)
    sibling = NS(id=5, parent_id=2)

    ordered = parents_first([grandchild, child, root_a, sibling, root_b])

    assert [ds.id for ds in ordered] == [2, 1, 3, 5, 4]


def test_unknown_parent_counts_as_root():
    assert [ds.id for ds in parents_first([NS(id=7, parent_id=99)])] == [7]
