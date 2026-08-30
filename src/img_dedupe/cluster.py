"""Union-find clustering of near-duplicate images.

Images are nodes; an edge is drawn between any pair whose perceptual hash
Hamming distance is at or under a threshold. Union-find (disjoint set union)
then collapses the pairwise-under-threshold graph into connected components,
so a chain of similar images (A close to B, B close to C, but A not directly
close to C) still ends up in one group -- exactly like transitive closure
over the "is near-duplicate of" edges.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field


class UnionFind:
    """Disjoint-set-union over integer indices, with union by rank and
    path-compressed find for near-constant-time operations."""

    def __init__(self, size: int) -> None:
        self._parent = list(range(size))
        self._rank = [0] * size

    def find(self, x: int) -> int:
        root = x
        while self._parent[root] != root:
            root = self._parent[root]
        # Path compression: point every visited node directly at the root.
        while self._parent[x] != root:
            self._parent[x], x = root, self._parent[x]
        return root

    def union(self, a: int, b: int) -> None:
        root_a, root_b = self.find(a), self.find(b)
        if root_a == root_b:
            return
        if self._rank[root_a] < self._rank[root_b]:
            root_a, root_b = root_b, root_a
        self._parent[root_b] = root_a
        if self._rank[root_a] == self._rank[root_b]:
            self._rank[root_a] += 1

    def connected(self, a: int, b: int) -> bool:
        return self.find(a) == self.find(b)

    def groups(self) -> list[list[int]]:
        """Return each connected component as a sorted list of member indices."""
        buckets: dict[int, list[int]] = {}
        for i in range(len(self._parent)):
            buckets.setdefault(self.find(i), []).append(i)
        return [sorted(members) for members in buckets.values()]


@dataclass
class PairEdge:
    """A pairwise similarity edge below the clustering threshold."""

    i: int
    j: int
    distance: int


@dataclass
class ClusterResult:
    groups: list[list[int]]
    edges: list[PairEdge] = field(default_factory=list)


def cluster_by_distance(
    n: int,
    distance_fn: Callable[[int, int], int],
    threshold: int,
) -> ClusterResult:
    """Cluster ``n`` items using pairwise ``distance_fn(i, j)`` under ``threshold``.

    ``distance_fn`` is called for every unordered pair ``(i, j)`` with
    ``i < j``. This is intentionally O(n^2) in the number of items -- exact
    and simple, appropriate for the batch, review-before-delete workflow
    this tool is built for.
    """
    uf = UnionFind(n)
    edges: list[PairEdge] = []
    for i in range(n):
        for j in range(i + 1, n):
            distance = distance_fn(i, j)
            if distance <= threshold:
                uf.union(i, j)
                edges.append(PairEdge(i, j, distance))
    return ClusterResult(groups=uf.groups(), edges=edges)
