from __future__ import annotations

from img_dedupe.cluster import ClusterResult, UnionFind, cluster_by_distance


def test_union_find_starts_all_singletons() -> None:
    uf = UnionFind(5)
    groups = uf.groups()
    assert sorted(groups) == [[0], [1], [2], [3], [4]]


def test_union_find_basic_union() -> None:
    uf = UnionFind(4)
    uf.union(0, 1)
    assert uf.connected(0, 1)
    assert not uf.connected(0, 2)


def test_union_find_chaining_transitive_closure() -> None:
    """A -- B -- C should end up in one group even though A and C are never
    unioned directly. This is the transitive-closure behaviour the whole
    clustering approach depends on."""
    uf = UnionFind(3)
    uf.union(0, 1)
    uf.union(1, 2)
    assert uf.connected(0, 2)
    groups = uf.groups()
    assert groups == [[0, 1, 2]]


def test_union_find_multiple_disjoint_groups() -> None:
    uf = UnionFind(6)
    uf.union(0, 1)
    uf.union(2, 3)
    groups = sorted(uf.groups())
    assert groups == [[0, 1], [2, 3], [4], [5]]


def test_union_find_repeated_union_is_idempotent() -> None:
    uf = UnionFind(3)
    uf.union(0, 1)
    uf.union(0, 1)
    uf.union(1, 0)
    assert uf.groups() == [[0, 1], [2]]


def test_cluster_by_distance_groups_close_pairs() -> None:
    # distances: (0,1)=2 (0,2)=20 (1,2)=20
    def distance_fn(i: int, j: int) -> int:
        table = {(0, 1): 2, (0, 2): 20, (1, 2): 20}
        return table[(min(i, j), max(i, j))]

    result = cluster_by_distance(3, distance_fn, threshold=5)
    assert sorted(result.groups) == [[0, 1], [2]]


def test_cluster_by_distance_chains_through_intermediate_item() -> None:
    # 0 close to 1 (dist 3), 1 close to 2 (dist 3), 0 far from 2 (dist 20)
    def distance_fn(i: int, j: int) -> int:
        table = {(0, 1): 3, (1, 2): 3, (0, 2): 20}
        return table[(min(i, j), max(i, j))]

    result = cluster_by_distance(3, distance_fn, threshold=5)
    assert result.groups == [[0, 1, 2]]


def test_cluster_by_distance_no_edges_all_singletons() -> None:
    def distance_fn(i: int, j: int) -> int:
        return 999

    result = cluster_by_distance(4, distance_fn, threshold=1)
    assert sorted(result.groups) == [[0], [1], [2], [3]]
    assert result.edges == []


def test_cluster_by_distance_empty_input() -> None:
    result = cluster_by_distance(0, lambda i, j: 0, threshold=1)
    assert result.groups == []


def test_cluster_result_records_edges() -> None:
    def distance_fn(i: int, j: int) -> int:
        return 1

    result: ClusterResult = cluster_by_distance(3, distance_fn, threshold=5)
    assert len(result.edges) == 3  # all 3 pairs among 3 items
    assert all(e.distance == 1 for e in result.edges)
