#!/usr/bin/env python3
"""Graph Quality Metrics Analyzer.

A beautiful TUI for analyzing knowledge graph quality metrics.
Uses direct SQL queries against Apache AGE internal tables for performance.

Usage:
    uv run python scripts/graph_metrics.py

Environment Variables:
    KARTOGRAPH_DB_HOST: Database host (default: localhost)
    KARTOGRAPH_DB_PORT: Database port (default: 5432)
    KARTOGRAPH_DB_DATABASE: Database name (default: kartograph)
    KARTOGRAPH_DB_USERNAME: Database user (default: kartograph)
    KARTOGRAPH_DB_PASSWORD: Database password
    KARTOGRAPH_DB_GRAPH_NAME: AGE graph name (default: kartograph_graph)
"""

from __future__ import annotations

import os
import random
import re
import sys
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any, Sequence

import psycopg2
from rich import box
from rich.console import Console, Group
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
)
from rich.table import Table
from rich.text import Text


console = Console()


# =============================================================================
# HELPERS: Generic utilities for reducing code duplication
# =============================================================================


@dataclass
class Threshold:
    """A threshold level with associated style and label."""

    min_value: float
    style: str
    label: str


def style_by_threshold(
    value: float,
    thresholds: list[Threshold],
    default_style: str = "dim",
    default_label: str = "Unknown",
) -> tuple[str, str]:
    """Return (style, label) based on value against thresholds.

    Thresholds should be ordered from highest to lowest min_value.
    """
    for t in thresholds:
        if value >= t.min_value:
            return t.style, t.label
    return default_style, default_label


@dataclass
class Bucket:
    """Definition of a bucket for value distribution."""

    label: str
    max_value: float | None  # None means infinity


def bucketize(values: Sequence[float | int], buckets: list[Bucket]) -> dict[str, int]:
    """Distribute values into labeled buckets.

    Buckets should be ordered from lowest max_value to highest.
    A value goes into the first bucket where value <= max_value.
    """
    result = {b.label: 0 for b in buckets}
    for v in values:
        for b in buckets:
            if b.max_value is None or v <= b.max_value:
                result[b.label] += 1
                break
    return result


def render_bar(pct: float, width: int, color: str) -> str:
    """Render a progress bar string."""
    filled = int(pct * width)
    return f"[{color}]{'█' * filled}[/]{'░' * (width - filled)}"


def create_distribution_table(
    distribution: dict[str, int],
    colors: list[str],
    label_width: int = 12,
    bar_width: int = 15,
    label_map: dict[str, str] | None = None,
) -> Table:
    """Create a standard distribution table with bars."""
    total = sum(distribution.values())
    table = Table(show_header=False, box=None, padding=(0, 0), show_edge=False)
    table.add_column("Label", width=label_width)
    table.add_column("Bar", width=bar_width)
    table.add_column("Value", justify="right", width=8)

    for i, (bucket, count) in enumerate(distribution.items()):
        pct = count / total if total > 0 else 0
        color = colors[i % len(colors)]
        label = label_map.get(bucket, bucket) if label_map else bucket
        bar = render_bar(pct, bar_width, color)
        table.add_row(f"[dim]{label}[/]", bar, f"[{color}]{count:,}[/]")

    return table


def create_ranked_table(
    items: list[tuple],
    columns: list[tuple[str, str, str]],  # (name, style, width_or_ratio)
    top_n: int = 10,
    top_style: str = "bold yellow",
    mid_style: str = "dim",
) -> Table:
    """Create a ranked table (e.g., top hubs, top centrality nodes)."""
    table = Table(show_header=True, box=box.SIMPLE, padding=(0, 1), expand=True)
    table.add_column("#", style="dim", width=3)

    for name, style, width in columns:
        if width.startswith("ratio:"):
            table.add_column(name, style=style, ratio=int(width.split(":")[1]))
        else:
            table.add_column(
                name,
                style=style,
                width=int(width),
                justify="right" if width.isdigit() else "left",
            )

    for i, item in enumerate(items[:top_n], 1):
        rank_style = top_style if i <= 3 else mid_style
        row = [f"[{rank_style}]{i}[/]"] + [str(v) for v in item]
        table.add_row(*row)

    return table


# =============================================================================
# CONFIGURATION
# =============================================================================


@dataclass
class MetricsConfig:
    """Configuration for graph metrics computation thresholds."""

    # Clustering coefficient
    clustering_sample_threshold: int = 50000
    clustering_hub_sample: int = 500
    clustering_random_sample: int = 9500

    # Path length analysis
    path_sample_size: int = 2000
    path_hub_sample: int = 200
    path_max_depth: int = 10

    # Centrality
    centrality_sample_pairs: int = 1000
    centrality_max_depth: int = 8
    pagerank_iterations: int = 10

    # Community detection
    community_max_iterations: int = 20

    # Reciprocity
    reciprocity_sample_size: int = 1000

    # Results
    top_hubs_count: int = 15
    top_centrality_count: int = 10
    top_communities_count: int = 5


DEFAULT_CONFIG = MetricsConfig()


# =============================================================================
# METRICS DATA MODEL
# =============================================================================


@dataclass
class GraphMetrics:
    """Container for all computed graph metrics."""

    # Basic counts
    total_nodes: int
    total_edges: int
    node_labels: dict[str, int]
    edge_labels: dict[str, int]

    # Connectivity
    connected_components: int
    largest_component_size: int
    largest_component_ratio: float
    orphan_nodes: int
    orphan_node_ratio: float

    # Degree statistics
    avg_degree: float
    min_degree: int
    max_degree: int
    median_degree: float
    degree_std_dev: float
    edge_density: float
    top_hub_nodes: list[tuple[str, str, int]]
    degree_distribution: dict[str, int]

    # Clustering coefficient
    avg_clustering_coefficient: float
    clustering_distribution: dict[str, int]

    # Path length analysis
    avg_path_length: float
    diameter_estimate: int
    path_length_distribution: dict[str, int]

    # Centrality scores
    top_betweenness_nodes: list[tuple[str, str, float]]
    top_pagerank_nodes: list[tuple[str, str, float]]

    # Schema quality
    orphan_node_types: list[str]
    orphan_edge_types: list[str]
    type_imbalance_score: float

    # Reciprocity analysis
    reciprocity_score: float
    unbalanced_relationships: list[tuple[str, str, int, int]]

    # Hub dependency
    hub_dependency_score: float
    graph_resilience: str

    # Community detection
    num_communities: int
    largest_community_size: int
    community_size_distribution: dict[str, int]
    modularity_estimate: float
    top_communities: list[tuple[int, int, str]]


# =============================================================================
# DATABASE LAYER
# =============================================================================


def get_connection():
    """Create a database connection using environment variables."""
    return psycopg2.connect(
        host=os.getenv("KARTOGRAPH_DB_HOST", "localhost"),
        port=int(os.getenv("KARTOGRAPH_DB_PORT", "5432")),
        database=os.getenv("KARTOGRAPH_DB_DATABASE", "kartograph"),
        user=os.getenv("KARTOGRAPH_DB_USERNAME", "kartograph"),
        password=os.getenv("KARTOGRAPH_DB_PASSWORD", "kartograph_dev_password"),
    )


def execute_sql(
    conn, query: str, params: tuple = (), commit: bool = False
) -> list[Any]:
    """Execute a SQL query and return results."""
    with conn.cursor() as cursor:
        cursor.execute(query, params)
        results = cursor.fetchall()
    if commit:
        conn.commit()
    return results


# =============================================================================
# GRAPH DATA LOADING
# =============================================================================


@dataclass
class GraphData:
    """Raw graph data loaded from database."""

    node_labels: dict[str, int]  # label -> count
    edge_labels: dict[str, int]  # label -> count
    total_nodes: int
    total_edges: int
    node_degrees: dict[int, int]  # node_id -> degree
    node_info: dict[int, tuple[str, Any]]  # node_id -> (label, properties)
    adjacency: dict[int, set[int]]  # node_id -> neighbor_ids


def load_graph_data(conn, graph_name: str, progress: Progress) -> GraphData:
    """Load all graph data from database."""

    # Discover schema
    task = progress.add_task("[cyan]Discovering schema...", total=2)

    vertex_labels = execute_sql(
        conn,
        """
        SELECT l.name, l.relation::regclass::text as table_name
        FROM ag_catalog.ag_label l
        JOIN ag_catalog.ag_graph g ON l.graph = g.graphid
        WHERE g.name = %s AND l.kind = 'v' AND l.name != '_ag_label_vertex'
    """,
        (graph_name,),
    )
    conn.commit()
    progress.advance(task)

    edge_labels_info = execute_sql(
        conn,
        """
        SELECT l.name, l.relation::regclass::text as table_name
        FROM ag_catalog.ag_label l
        JOIN ag_catalog.ag_graph g ON l.graph = g.graphid
        WHERE g.name = %s AND l.kind = 'e' AND l.name != '_ag_label_edge'
    """,
        (graph_name,),
    )
    conn.commit()
    progress.advance(task)

    # Count nodes
    task = progress.add_task("[green]Counting nodes...", total=len(vertex_labels))
    node_labels = {}
    total_nodes = 0
    for label_name, table_name in vertex_labels:
        count = execute_sql(conn, f"SELECT COUNT(*) FROM {table_name}", commit=True)[0][
            0
        ]
        node_labels[label_name] = count
        total_nodes += count
        progress.advance(task)
    node_labels = dict(sorted(node_labels.items(), key=lambda x: -x[1]))

    # Count edges
    task = progress.add_task("[yellow]Counting edges...", total=len(edge_labels_info))
    edge_labels = {}
    total_edges = 0
    for label_name, table_name in edge_labels_info:
        count = execute_sql(conn, f"SELECT COUNT(*) FROM {table_name}", commit=True)[0][
            0
        ]
        edge_labels[label_name] = count
        total_edges += count
        progress.advance(task)
    edge_labels = dict(sorted(edge_labels.items(), key=lambda x: -x[1]))

    # Compute degrees and build adjacency
    task = progress.add_task(
        "[magenta]Computing degrees...",
        total=len(vertex_labels) + len(edge_labels_info) * 2,
    )

    node_degrees: dict[int, int] = defaultdict(int)
    node_info: dict[int, tuple[str, Any]] = {}
    adjacency: dict[int, set[int]] = defaultdict(set)

    for label_name, table_name in vertex_labels:
        for node_id, props in execute_sql(
            conn, f"SELECT id, properties FROM {table_name}", commit=True
        ):
            node_info[node_id] = (label_name, props)
            node_degrees[node_id] = 0
        progress.advance(task)

    for _, table_name in edge_labels_info:
        for node_id, count in execute_sql(
            conn,
            f"SELECT start_id, COUNT(*) FROM {table_name} GROUP BY start_id",
            commit=True,
        ):
            node_degrees[node_id] += count
        progress.advance(task)

        for node_id, count in execute_sql(
            conn,
            f"SELECT end_id, COUNT(*) FROM {table_name} GROUP BY end_id",
            commit=True,
        ):
            node_degrees[node_id] += count
        progress.advance(task)

    # Build adjacency (for clustering, paths, etc.)
    for _, table_name in edge_labels_info:
        for start_id, end_id in execute_sql(
            conn, f"SELECT start_id, end_id FROM {table_name}", commit=True
        ):
            adjacency[start_id].add(end_id)
            adjacency[end_id].add(start_id)

    return GraphData(
        node_labels=node_labels,
        edge_labels=edge_labels,
        total_nodes=total_nodes,
        total_edges=total_edges,
        node_degrees=dict(node_degrees),
        node_info=node_info,
        adjacency=dict(adjacency),
    )


# =============================================================================
# METRIC COMPUTATIONS (extracted from monolithic function)
# =============================================================================


def extract_slug(props: Any, node_id: int) -> str:
    """Extract slug or id from node properties."""
    try:
        props_str = str(props)
        for key in ['"slug":', '"id":']:
            if key in props_str:
                match = re.search(rf'{key}\s*"([^"]+)"', props_str)
                if match:
                    return match.group(1)
    except Exception:
        pass
    return str(node_id)


def compute_degree_stats(data: GraphData, config: MetricsConfig) -> dict:
    """Compute degree-related statistics."""
    degrees = list(data.node_degrees.values())

    if not degrees:
        return {
            "avg_degree": 0,
            "min_degree": 0,
            "max_degree": 0,
            "median_degree": 0,
            "degree_std_dev": 0,
            "edge_density": 0,
            "orphan_nodes": 0,
            "orphan_node_ratio": 0,
            "degree_distribution": {},
            "top_hub_nodes": [],
        }

    avg_degree = sum(degrees) / len(degrees)
    sorted_degrees = sorted(degrees)
    median_degree = sorted_degrees[len(sorted_degrees) // 2]
    variance = sum((d - avg_degree) ** 2 for d in degrees) / len(degrees)

    orphan_nodes = sum(1 for d in degrees if d == 0)
    possible_edges = (
        data.total_nodes * (data.total_nodes - 1) if data.total_nodes > 1 else 1
    )

    # Bucketing
    degree_buckets = bucketize(
        degrees,
        [
            Bucket("0", 0),
            Bucket("1", 1),
            Bucket("2-5", 5),
            Bucket("6-10", 10),
            Bucket("11-50", 50),
            Bucket("51-100", 100),
            Bucket("100+", None),
        ],
    )

    # Top hubs
    degree_with_info = [
        (
            nid,
            data.node_info.get(nid, ("unknown", {}))[0],
            data.node_info.get(nid, ("unknown", {}))[1],
            deg,
        )
        for nid, deg in data.node_degrees.items()
    ]
    sorted_by_degree = sorted(degree_with_info, key=lambda x: -x[3])[
        : config.top_hubs_count
    ]
    top_hubs = [
        (extract_slug(props, nid), label, deg)
        for nid, label, props, deg in sorted_by_degree
    ]

    return {
        "avg_degree": avg_degree,
        "min_degree": min(degrees),
        "max_degree": max(degrees),
        "median_degree": median_degree,
        "degree_std_dev": variance**0.5,
        "edge_density": data.total_edges / possible_edges,
        "orphan_nodes": orphan_nodes,
        "orphan_node_ratio": orphan_nodes / data.total_nodes
        if data.total_nodes > 0
        else 0,
        "degree_distribution": degree_buckets,
        "top_hub_nodes": top_hubs,
    }


def compute_connectivity(
    data: GraphData, orphan_ratio: float, avg_degree: float
) -> dict:
    """Estimate connectivity metrics."""
    orphan_nodes = sum(1 for d in data.node_degrees.values() if d == 0)

    if orphan_ratio < 0.05 and avg_degree >= 2:
        largest_component_size = data.total_nodes - orphan_nodes
        estimated_components = 1 + orphan_nodes
    else:
        largest_component_size = data.total_nodes - orphan_nodes
        estimated_components = max(1, orphan_nodes + 1)

    return {
        "connected_components": estimated_components,
        "largest_component_size": largest_component_size,
        "largest_component_ratio": largest_component_size / data.total_nodes
        if data.total_nodes > 0
        else 0,
    }


def compute_clustering(
    data: GraphData, config: MetricsConfig, progress: Progress
) -> dict:
    """Compute clustering coefficient."""
    task = progress.add_task("[blue]Computing clustering...", total=100)

    eligible_nodes = [n for n, d in data.node_degrees.items() if d >= 2]

    # Sampling
    if len(eligible_nodes) <= config.clustering_sample_threshold:
        sample_nodes = eligible_nodes
    else:
        sorted_nodes = sorted(
            eligible_nodes, key=lambda n: data.node_degrees[n], reverse=True
        )
        sample_nodes = sorted_nodes[: config.clustering_hub_sample] + random.sample(
            sorted_nodes[config.clustering_hub_sample :],
            min(
                config.clustering_random_sample,
                len(sorted_nodes) - config.clustering_hub_sample,
            ),
        )

    progress.advance(task, 30)

    # Calculate clustering coefficients
    clustering_coefficients = []
    step_size = max(1, len(sample_nodes) // 60)

    for i, node_id in enumerate(sample_nodes):
        neighbors = data.adjacency.get(node_id, set())
        k = len(neighbors)
        if k < 2:
            continue

        neighbor_list = list(neighbors)
        edges_between = sum(
            1
            for j, n1 in enumerate(neighbor_list)
            for n2 in neighbor_list[j + 1 :]
            if n2 in data.adjacency.get(n1, set())
        )

        possible = k * (k - 1) // 2
        clustering_coefficients.append(edges_between / possible if possible > 0 else 0)

        if i % step_size == 0:
            progress.advance(task, 1)

    avg_clustering = (
        sum(clustering_coefficients) / len(clustering_coefficients)
        if clustering_coefficients
        else 0
    )

    # Bucketing
    clustering_distribution = bucketize(
        clustering_coefficients,
        [
            Bucket("0.0", 0),
            Bucket("0.0-0.1", 0.1),
            Bucket("0.1-0.3", 0.3),
            Bucket("0.3-0.5", 0.5),
            Bucket("0.5-0.7", 0.7),
            Bucket("0.7-1.0", 0.99999),
            Bucket("1.0", None),
        ],
    )

    progress.update(task, completed=100)
    return {
        "avg_clustering_coefficient": avg_clustering,
        "clustering_distribution": clustering_distribution,
    }


def compute_paths(data: GraphData, config: MetricsConfig, progress: Progress) -> dict:
    """Compute path length statistics."""
    task = progress.add_task("[cyan]Analyzing paths...", total=100)

    eligible = [n for n, d in data.node_degrees.items() if d >= 2]
    sample_count = min(config.path_sample_size, len(eligible))

    if len(eligible) > sample_count:
        sorted_by_deg = sorted(
            eligible, key=lambda n: data.node_degrees[n], reverse=True
        )
        remaining = sample_count - config.path_hub_sample
        sources = sorted_by_deg[: config.path_hub_sample] + random.sample(
            sorted_by_deg[config.path_hub_sample :],
            min(remaining, len(sorted_by_deg) - config.path_hub_sample),
        )
    else:
        sources = eligible

    all_paths = []
    max_path = 0

    for i, source in enumerate(sources[:sample_count]):
        visited = {source: 0}
        queue = deque([source])

        while queue:
            current = queue.popleft()
            dist = visited[current]
            if dist >= config.path_max_depth:
                continue

            for neighbor in data.adjacency.get(current, set()):
                if neighbor not in visited:
                    visited[neighbor] = dist + 1
                    queue.append(neighbor)
                    all_paths.append(dist + 1)
                    max_path = max(max_path, dist + 1)

        if i % 200 == 0:
            progress.advance(task, 5)

    path_distribution = bucketize(
        all_paths,
        [
            Bucket("1", 1),
            Bucket("2", 2),
            Bucket("3", 3),
            Bucket("4", 4),
            Bucket("5", 5),
            Bucket("6+", None),
        ],
    )

    progress.update(task, completed=100)
    return {
        "avg_path_length": sum(all_paths) / len(all_paths) if all_paths else 0,
        "diameter_estimate": max_path,
        "path_length_distribution": path_distribution,
    }


def compute_centrality(
    data: GraphData, config: MetricsConfig, progress: Progress
) -> dict:
    """Compute centrality metrics (betweenness and PageRank)."""
    task = progress.add_task("[magenta]Computing centrality...", total=100)

    eligible = [n for n, d in data.node_degrees.items() if d >= 2]

    # Betweenness (sample-based)
    betweenness: dict[int, int] = defaultdict(int)
    sample_pairs = [
        random.sample(eligible, 2)
        for _ in range(min(config.centrality_sample_pairs, len(eligible)))
    ]

    for idx, (src, dst) in enumerate(sample_pairs):
        visited = {src: (0, None)}
        queue = deque([src])
        found = False

        while queue and not found:
            current = queue.popleft()
            if current == dst:
                found = True
                break
            dist = visited[current][0]
            if dist >= config.centrality_max_depth:
                continue
            for neighbor in data.adjacency.get(current, set()):
                if neighbor not in visited:
                    visited[neighbor] = (dist + 1, current)
                    queue.append(neighbor)

        if found:
            node = dst
            while node is not None:
                parent = visited[node][1]
                if parent is not None and node not in (src, dst):
                    betweenness[node] += 1
                node = parent

        if idx % 100 == 0:
            progress.advance(task, 5)

    top_betweenness = [
        (
            extract_slug(data.node_info.get(nid, ("", {}))[1], nid),
            data.node_info.get(nid, ("unknown", {}))[0],
            count / len(sample_pairs) if sample_pairs else 0,
        )
        for nid, count in sorted(betweenness.items(), key=lambda x: -x[1])[
            : config.top_centrality_count
        ]
    ]

    progress.update(task, completed=60)

    # PageRank
    pagerank = {n: 1.0 / len(data.node_degrees) for n in data.node_degrees}
    damping = 0.85

    for _ in range(config.pagerank_iterations):
        new_pr = {}
        for node in data.node_degrees:
            rank = (1 - damping) / len(data.node_degrees)
            for neighbor in data.adjacency.get(node, set()):
                out_deg = len(data.adjacency.get(neighbor, set()))
                if out_deg > 0:
                    rank += damping * pagerank.get(neighbor, 0) / out_deg
            new_pr[node] = rank
        pagerank = new_pr

    top_pagerank = [
        (
            extract_slug(data.node_info.get(nid, ("", {}))[1], nid),
            data.node_info.get(nid, ("unknown", {}))[0],
            score,
        )
        for nid, score in sorted(pagerank.items(), key=lambda x: -x[1])[
            : config.top_centrality_count
        ]
    ]

    progress.update(task, completed=100)
    return {
        "top_betweenness_nodes": top_betweenness,
        "top_pagerank_nodes": top_pagerank,
    }


def compute_schema_quality(data: GraphData) -> dict:
    """Compute schema quality metrics."""
    orphan_node_types = [
        label for label, count in data.node_labels.items() if count <= 2
    ]
    orphan_edge_types = [
        label for label, count in data.edge_labels.items() if count <= 2
    ]

    # Gini coefficient for type imbalance
    values = sorted(data.node_labels.values())
    if not values or sum(values) == 0:
        gini = 0.0
    else:
        n = len(values)
        cumsum = sum((2 * (i + 1) - n - 1) * v for i, v in enumerate(values))
        gini = cumsum / (n * sum(values))

    return {
        "orphan_node_types": orphan_node_types,
        "orphan_edge_types": orphan_edge_types,
        "type_imbalance_score": gini,
    }


def compute_reciprocity(
    data: GraphData, config: MetricsConfig, progress: Progress
) -> dict:
    """Compute reciprocity metrics."""
    task = progress.add_task("[yellow]Analyzing schema...", total=100)

    # Find inverse pairs
    edge_types = list(data.edge_labels.keys())
    inverse_pairs = []

    for i, t1 in enumerate(edge_types):
        for t2 in edge_types[i + 1 :]:
            t1_norm = t1.upper().replace("_", "")
            t2_norm = t2.upper().replace("_", "")

            is_inverse = (
                t2_norm == t1_norm + "BY"
                or t1_norm == t2_norm + "BY"
                or t2_norm == t1_norm + "EDBY"
                or t1_norm == t2_norm + "EDBY"
            )

            if is_inverse:
                c1, c2 = data.edge_labels[t1], data.edge_labels[t2]
                if abs(c1 - c2) / max(c1, c2, 1) > 0.05:
                    inverse_pairs.append((t1, t2, c1, c2))

    progress.advance(task, 50)

    # Overall reciprocity
    total_checked = 0
    total_reciprocal = 0
    for node in list(data.node_degrees.keys())[: config.reciprocity_sample_size]:
        for neighbor in data.adjacency.get(node, set()):
            total_checked += 1
            if node in data.adjacency.get(neighbor, set()):
                total_reciprocal += 1

    progress.update(task, completed=100)
    return {
        "reciprocity_score": total_reciprocal / max(total_checked, 1),
        "unbalanced_relationships": sorted(
            inverse_pairs, key=lambda x: abs(x[2] - x[3]), reverse=True
        )[:5],
    }


def compute_resilience(data: GraphData, progress: Progress) -> dict:
    """Compute hub dependency / resilience metrics."""
    task = progress.add_task("[red]Analyzing resilience...", total=100)

    top_5_ids = {
        nid for nid, _ in sorted(data.node_degrees.items(), key=lambda x: -x[1])[:5]
    }

    edges_through_hubs = (
        sum(
            1
            for node, neighbors in data.adjacency.items()
            for neighbor in neighbors
            if node in top_5_ids or neighbor in top_5_ids
        )
        // 2
    )  # Undirected, counted twice

    hub_dep = edges_through_hubs / max(data.total_edges, 1)

    if hub_dep > 0.5:
        resilience = "fragile"
    elif hub_dep > 0.25:
        resilience = "moderate"
    else:
        resilience = "robust"

    progress.update(task, completed=100)
    return {"hub_dependency_score": hub_dep, "graph_resilience": resilience}


def compute_communities(
    data: GraphData, config: MetricsConfig, progress: Progress
) -> dict:
    """Detect communities using label propagation."""
    task = progress.add_task("[green]Detecting communities...", total=100)

    node_community = {n: n for n in data.node_degrees}
    connected = [n for n, d in data.node_degrees.items() if d > 0]

    for iteration in range(config.community_max_iterations):
        random.shuffle(connected)
        changes = 0

        for node in connected:
            neighbors = data.adjacency.get(node, set())
            if not neighbors:
                continue

            label_counts: dict[int, int] = defaultdict(int)
            for neighbor in neighbors:
                label_counts[node_community[neighbor]] += 1

            if label_counts:
                max_count = max(label_counts.values())
                best = min(lbl for lbl, cnt in label_counts.items() if cnt == max_count)
                if node_community[node] != best:
                    node_community[node] = best
                    changes += 1

        progress.advance(task, 4)
        if changes == 0:
            break

    progress.update(task, completed=80)

    # Gather stats
    community_sizes: dict[int, int] = defaultdict(int)
    community_members: dict[int, list[int]] = defaultdict(list)

    for node, comm in node_community.items():
        community_sizes[comm] += 1
        community_members[comm].append(node)

    real_communities = {c: s for c, s in community_sizes.items() if s > 1}

    size_distribution = bucketize(
        list(real_communities.values()),
        [
            Bucket("2-5", 5),
            Bucket("6-20", 20),
            Bucket("21-100", 100),
            Bucket("101-500", 500),
            Bucket("501-1000", 1000),
            Bucket("1000+", None),
        ],
    )

    # Top communities with sample labels
    top_communities = []
    for comm_id, size in sorted(real_communities.items(), key=lambda x: -x[1])[
        : config.top_communities_count
    ]:
        members = community_members[comm_id][:10]
        labels = {data.node_info.get(m, ("unknown", {}))[0] for m in members}
        top_communities.append((comm_id, size, ", ".join(list(labels)[:3])))

    # Modularity estimate
    internal_edges = (
        sum(
            1
            for comm_id, members in community_members.items()
            if len(members) >= 2
            for member in members
            for neighbor in data.adjacency.get(member, set())
            if neighbor in set(members)
        )
        // 2
    )

    modularity = min(1.0, (internal_edges / max(data.total_edges, 1)) * 1.5)

    progress.update(task, completed=100)
    return {
        "num_communities": len(real_communities),
        "largest_community_size": max(real_communities.values())
        if real_communities
        else 0,
        "community_size_distribution": size_distribution,
        "modularity_estimate": modularity,
        "top_communities": top_communities,
    }


# =============================================================================
# MAIN METRICS COMPUTATION (orchestrator)
# =============================================================================


def compute_metrics(
    conn, graph_name: str, progress: Progress, config: MetricsConfig = DEFAULT_CONFIG
) -> GraphMetrics:
    """Compute all graph metrics."""

    # Load data
    data = load_graph_data(conn, graph_name, progress)

    # Compute individual metrics
    degree_stats = compute_degree_stats(data, config)
    connectivity = compute_connectivity(
        data, degree_stats["orphan_node_ratio"], degree_stats["avg_degree"]
    )
    clustering = compute_clustering(data, config, progress)
    paths = compute_paths(data, config, progress)
    centrality = compute_centrality(data, config, progress)
    schema = compute_schema_quality(data)
    reciprocity = compute_reciprocity(data, config, progress)
    resilience = compute_resilience(data, progress)
    communities = compute_communities(data, config, progress)

    return GraphMetrics(
        total_nodes=data.total_nodes,
        total_edges=data.total_edges,
        node_labels=data.node_labels,
        edge_labels=data.edge_labels,
        **connectivity,
        orphan_nodes=degree_stats["orphan_nodes"],
        orphan_node_ratio=degree_stats["orphan_node_ratio"],
        avg_degree=degree_stats["avg_degree"],
        min_degree=degree_stats["min_degree"],
        max_degree=degree_stats["max_degree"],
        median_degree=degree_stats["median_degree"],
        degree_std_dev=degree_stats["degree_std_dev"],
        edge_density=degree_stats["edge_density"],
        top_hub_nodes=degree_stats["top_hub_nodes"],
        degree_distribution=degree_stats["degree_distribution"],
        **clustering,
        **paths,
        **centrality,
        **schema,
        **reciprocity,
        **resilience,
        **communities,
    )


# =============================================================================
# UI PANELS
# =============================================================================


def create_header(graph_name: str) -> Panel:
    """Create the header panel."""
    title = Text()
    title.append("  KARTOGRAPH  ", style="bold white on blue")
    title.append("  Graph Quality Analyzer  ", style="bold cyan")
    subtitle = Text(f"Analyzing: {graph_name}", style="dim")
    return Panel(
        Group(title, subtitle), box=box.DOUBLE, border_style="blue", padding=(0, 2)
    )


def create_section_header(title: str, subtitle: str = "") -> Panel:
    """Create a section header."""
    content = Text()
    content.append(f"  {title}  ", style="bold white on dark_blue")
    if subtitle:
        content.append(f"  {subtitle}", style="dim")
    return Panel(content, box=box.SIMPLE, padding=(0, 0), style="dim")


def create_overview_panel(m: GraphMetrics) -> Panel:
    """Create the overview statistics panel."""
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Metric", style="dim")
    table.add_column("Value", justify="right", style="bold")
    table.add_row("Total Nodes", f"[green]{m.total_nodes:,}[/]")
    table.add_row("Total Edges", f"[cyan]{m.total_edges:,}[/]")
    table.add_row("Node Types", f"[yellow]{len(m.node_labels):,}[/]")
    table.add_row("Edge Types", f"[magenta]{len(m.edge_labels):,}[/]")
    table.add_row("", "")
    table.add_row("Edges/Node", f"[blue]{m.total_edges / m.total_nodes:.2f}[/]")
    table.add_row("Avg Degree", f"[blue]{m.avg_degree:.2f}[/]")
    return Panel(
        table, title="[bold]Overview[/]", border_style="green", box=box.ROUNDED
    )


def create_connectivity_panel(m: GraphMetrics) -> Panel:
    """Create the connectivity metrics panel."""
    style, status = style_by_threshold(
        m.largest_component_ratio,
        [
            Threshold(0.9, "bold green", "Excellent"),
            Threshold(0.7, "bold yellow", "Good"),
        ],
        "bold red",
        "Fragmented",
    )

    orphan_style, _ = style_by_threshold(
        1 - m.orphan_node_ratio,
        [
            Threshold(0.99, "green", ""),
            Threshold(0.95, "yellow", ""),
        ],
        "red",
        "",
    )

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Metric", style="dim")
    table.add_column("Value", justify="right")
    table.add_row("Connected", f"[{style}]{m.largest_component_ratio:.1%}[/]")
    table.add_row("Status", f"[{style}]{status}[/]")
    table.add_row("", "")
    table.add_row("Orphans", f"[{orphan_style}]{m.orphan_nodes:,}[/]")
    table.add_row("Orphan %", f"[{orphan_style}]{m.orphan_node_ratio:.1%}[/]")
    return Panel(
        table, title="[bold]Connectivity[/]", border_style="cyan", box=box.ROUNDED
    )


def create_degree_stats_panel(m: GraphMetrics) -> Panel:
    """Create the degree statistics panel."""
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Stat", style="dim")
    table.add_column("Value", justify="right", style="bold cyan")
    table.add_row("Min", str(m.min_degree))
    table.add_row("Median", str(int(m.median_degree)))
    table.add_row("Average", f"{m.avg_degree:.1f}")
    table.add_row("Max", f"[bold yellow]{m.max_degree:,}[/]")
    table.add_row("Std Dev", f"{m.degree_std_dev:.1f}")
    return Panel(
        table, title="[bold]Degree Stats[/]", border_style="magenta", box=box.ROUNDED
    )


def create_clustering_panel(m: GraphMetrics) -> Panel:
    """Create the clustering coefficient panel."""
    cc = m.avg_clustering_coefficient
    style, status = style_by_threshold(
        cc,
        [
            Threshold(0.5, "bold green", "Tight-knit"),
            Threshold(0.3, "bold cyan", "Well-grouped"),
            Threshold(0.15, "bold yellow", "Some clusters"),
            Threshold(0.05, "yellow", "Sparse"),
        ],
        "red",
        "No clusters",
    )

    bar_filled = (
        5 if cc > 0.5 else 4 if cc > 0.3 else 3 if cc > 0.15 else 2 if cc > 0.05 else 1
    )

    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("", width=18)
    table.add_row(f"[{style}]{cc:.0%}[/] [dim]clustered[/]")
    table.add_row("")
    table.add_row(f"[{style}]{'●' * bar_filled}[/][dim]{'○' * (5 - bar_filled)}[/]")
    table.add_row(f"[{style}]{status}[/]")
    table.add_row("")
    table.add_row("[dim italic]Good community[/]")
    table.add_row("[dim italic]structure[/]")
    return Panel(
        table, title="[bold]Clustering[/]", border_style="blue", box=box.ROUNDED
    )


def create_clustering_distribution_panel(m: GraphMetrics) -> Panel:
    """Create clustering distribution panel."""
    header = Text()
    header.append("If node A connects to B and C,\n", style="dim")
    header.append("do B and C also connect?\n\n", style="dim")

    label_map = {
        "0.0": "None connect",
        "0.0-0.1": "Almost none",
        "0.1-0.3": "Some do",
        "0.3-0.5": "About half",
        "0.5-0.7": "Most do",
        "0.7-1.0": "Nearly all",
        "1.0": "All connect",
    }
    colors = ["red", "orange1", "yellow", "green_yellow", "cyan", "green", "bold green"]

    table = create_distribution_table(
        m.clustering_distribution, colors, label_map=label_map
    )
    total = sum(m.clustering_distribution.values())

    return Panel(
        Group(header, table),
        title="[bold]Neighbor Connections[/]",
        subtitle=f"[dim]{total:,} nodes[/]",
        border_style="blue",
        box=box.ROUNDED,
    )


def create_degree_distribution_panel(m: GraphMetrics) -> Panel:
    """Create degree distribution panel."""
    colors = ["red", "yellow", "green", "cyan", "blue", "magenta", "white"]
    total = m.total_nodes
    max_bar = 25

    table = Table(show_header=True, box=None, padding=(0, 1))
    table.add_column("Range", style="dim", width=8)
    table.add_column("Count", justify="right", width=7)
    table.add_column("Distribution", width=max_bar + 8)

    for i, (bucket, count) in enumerate(m.degree_distribution.items()):
        pct = count / total if total > 0 else 0
        color = colors[i % len(colors)]
        bar = render_bar(pct, max_bar, color) + f" {pct:>5.1%}"
        table.add_row(bucket, f"{count:,}", bar)

    return Panel(
        table,
        title="[bold]Degree Distribution[/]",
        border_style="yellow",
        box=box.ROUNDED,
    )


def create_hub_nodes_panel(m: GraphMetrics) -> Panel:
    """Create top hub nodes panel."""
    table = Table(show_header=True, box=box.SIMPLE, padding=(0, 1), expand=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("Node", style="bold", ratio=2)
    table.add_column("Type", style="cyan", ratio=1)
    table.add_column("Connections", justify="right", style="green", width=12)

    for i, (name, label, degree) in enumerate(m.top_hub_nodes[:10], 1):
        rs = "bold yellow" if i <= 3 else "dim"
        ds = "bold green" if i <= 3 else "green" if i <= 6 else "dim green"
        table.add_row(f"[{rs}]{i}[/]", name, label, f"[{ds}]{degree:,}[/]")

    return Panel(
        table, title="[bold]Top Hub Nodes[/]", border_style="green", box=box.ROUNDED
    )


def create_labels_panel(
    labels: dict[str, int], total: int, title: str, style: str, color: str
) -> Panel:
    """Create a labels distribution panel (reusable for nodes and edges)."""
    table = Table(show_header=True, box=box.SIMPLE, padding=(0, 1), expand=True)
    table.add_column("Label", style=style, ratio=2)
    table.add_column("Count", justify="right", style="green", width=8)
    table.add_column("%", justify="right", style="dim", width=6)

    for label, count in list(labels.items())[:8]:
        table.add_row(label, f"{count:,}", f"{count / total * 100:.1f}%")

    remaining = len(labels) - 8
    if remaining > 0:
        table.add_row(f"[dim]... +{remaining} more[/]", "", "")

    return Panel(table, title=f"[bold]{title}[/]", border_style=color, box=box.ROUNDED)


def create_path_analysis_panel(m: GraphMetrics) -> Panel:
    """Create path length analysis panel."""
    apl = m.avg_path_length
    style, status = style_by_threshold(
        1 / max(apl, 0.1),
        [  # Invert so lower is better
            Threshold(0.33, "bold green", "Excellent"),
            Threshold(0.2, "cyan", "Good"),
        ],
        "yellow",
        "Long paths",
    )

    grid = Table.grid(padding=(0, 2))
    grid.add_column()
    grid.add_column()

    stats = Table(show_header=False, box=None, padding=(0, 1))
    stats.add_column("", width=16)
    stats.add_column("", width=10)
    stats.add_row("[dim]Average path:[/]", f"[{style}]{apl:.1f} hops[/]")
    stats.add_row("[dim]Status:[/]", f"[{style}]{status}[/]")
    stats.add_row("[dim]Diameter:[/]", f"[cyan]{m.diameter_estimate} hops[/]")

    dist = Table(show_header=False, box=None, padding=(0, 0))
    dist.add_column("Hops", width=5, style="dim")
    dist.add_column("Bar", width=12)
    dist.add_column("%", width=5, justify="right")

    total = sum(m.path_length_distribution.values())
    for bucket, count in m.path_length_distribution.items():
        pct = count / total if total > 0 else 0
        dist.add_row(bucket, render_bar(pct, 10, "cyan"), f"{pct:.0%}")

    grid.add_row(stats, dist)
    return Panel(
        grid,
        title="[bold]Path Length[/]",
        subtitle="[dim]How many hops to reach other nodes?[/]",
        border_style="cyan",
        box=box.ROUNDED,
    )


def create_centrality_panel(m: GraphMetrics) -> Panel:
    """Create centrality panel with PageRank and Betweenness."""
    grid = Table.grid(expand=True, padding=(0, 2))
    grid.add_column(ratio=1)
    grid.add_column(ratio=1)

    # PageRank
    pr = Table(show_header=True, box=box.SIMPLE, padding=(0, 1), expand=True)
    pr.add_column("#", style="dim", width=2)
    pr.add_column("Node", style="cyan", ratio=2)
    pr.add_column("Type", style="dim", ratio=1)
    pr.add_column("Score", justify="right", style="magenta", width=8)
    for i, (slug, label, score) in enumerate(m.top_pagerank_nodes[:5], 1):
        pr.add_row(str(i), slug, label, f"{score:.4f}")

    # Betweenness
    bt = Table(show_header=True, box=box.SIMPLE, padding=(0, 1), expand=True)
    bt.add_column("#", style="dim", width=2)
    bt.add_column("Node", style="cyan", ratio=2)
    bt.add_column("Type", style="dim", ratio=1)
    bt.add_column("Bridge %", justify="right", style="yellow", width=8)
    for i, (slug, label, score) in enumerate(m.top_betweenness_nodes[:5], 1):
        bt.add_row(str(i), slug, label, f"{score:.0%}")

    grid.add_row(
        Panel(
            pr,
            title="[magenta]PageRank[/] [dim](influence)[/]",
            box=box.SIMPLE,
            padding=(0, 0),
        ),
        Panel(
            bt,
            title="[yellow]Betweenness[/] [dim](bridges)[/]",
            box=box.SIMPLE,
            padding=(0, 0),
        ),
    )
    return Panel(
        grid,
        title="[bold]Centrality[/]",
        subtitle="[dim]Which nodes are most important?[/]",
        border_style="magenta",
        box=box.ROUNDED,
    )


def create_schema_quality_panel(m: GraphMetrics) -> Panel:
    """Create schema quality panel."""
    gini_style, gini_status = style_by_threshold(
        1 - m.type_imbalance_score,
        [
            Threshold(0.5, "green", "Balanced"),
            Threshold(0.3, "yellow", "Some imbalance"),
        ],
        "red",
        "Very imbalanced",
    )

    table = Table(show_header=False, box=None, padding=(0, 1), expand=True)
    table.add_column("")
    table.add_row(f"[dim]Type Balance:[/] [{gini_style}]{gini_status}[/]")
    table.add_row("")

    on, oe = len(m.orphan_node_types), len(m.orphan_edge_types)
    table.add_row(
        f"[yellow]{on}[/] [dim]rare node types (used 1-2 times)[/]"
        if on
        else "[green]No rare node types[/]"
    )
    table.add_row(
        f"[yellow]{oe}[/] [dim]rare edge types (used 1-2 times)[/]"
        if oe
        else "[green]No rare edge types[/]"
    )

    return Panel(
        table, title="[bold]Schema Quality[/]", border_style="yellow", box=box.ROUNDED
    )


def create_reciprocity_panel(m: GraphMetrics) -> Panel:
    """Create reciprocity panel."""
    style, status = style_by_threshold(
        m.reciprocity_score,
        [
            Threshold(0.8, "green", "Highly bidirectional"),
            Threshold(0.5, "cyan", "Mostly bidirectional"),
            Threshold(0.2, "yellow", "Mixed direction"),
        ],
        "dim",
        "Mostly one-way",
    )

    table = Table(show_header=False, box=None, padding=(0, 1), expand=True)
    table.add_column("")
    table.add_row(
        f"[{style}]{m.reciprocity_score:.0%}[/] [dim]of edges have a reverse edge[/]"
    )
    table.add_row(f"[dim]{status}[/]")

    if m.unbalanced_relationships:
        table.add_row("")
        table.add_row("[dim]Inverse pairs with mismatched counts:[/]")
        for t1, t2, c1, c2 in m.unbalanced_relationships[:2]:
            table.add_row(
                f"  [cyan]{t1}[/] [dim]({c1:,})[/] vs [cyan]{t2}[/] [dim]({c2:,})[/]"
            )
    else:
        table.add_row("")
        table.add_row("[green]All inverse pairs are balanced[/]")

    return Panel(
        table,
        title="[bold]Reciprocity[/]",
        subtitle="[dim]Are relationships bidirectional?[/]",
        border_style="blue",
        box=box.ROUNDED,
    )


def create_resilience_panel(m: GraphMetrics) -> Panel:
    """Create resilience panel."""
    if m.graph_resilience == "robust":
        style, icon, desc = "bold green", "●●●●●", "Graph would survive hub removal"
    elif m.graph_resilience == "moderate":
        style, icon, desc = "bold yellow", "●●●○○", "Some dependency on key hubs"
    else:
        style, icon, desc = "bold red", "●○○○○", "Heavy reliance on top hubs - fragile!"

    table = Table(show_header=False, box=None, padding=(0, 1), expand=True)
    table.add_column("")
    table.add_row(f"[{style}]{m.graph_resilience.upper()}[/] [{style}]{icon}[/]")
    table.add_row("")
    table.add_row(f"[dim]{m.hub_dependency_score:.0%} of edges touch top 5 hubs[/]")
    table.add_row("")
    table.add_row(f"[dim italic]{desc}[/]")

    border = "red" if m.graph_resilience == "fragile" else "green"
    return Panel(
        table,
        title="[bold]Resilience[/]",
        subtitle="[dim]Hub dependency risk[/]",
        border_style=border,
        box=box.ROUNDED,
    )


def create_community_panel(m: GraphMetrics) -> Panel:
    """Create community detection panel."""
    style, status = style_by_threshold(
        m.num_communities,
        [
            Threshold(50, "cyan", "Many communities"),
            Threshold(10, "green", "Good structure"),
            Threshold(1, "yellow", "Few communities"),
        ],
        "red",
        "No communities",
    )

    grid = Table.grid(expand=True, padding=(0, 2))
    grid.add_column(ratio=1)
    grid.add_column(ratio=1)

    stats = Table(show_header=False, box=None, padding=(0, 1))
    stats.add_column("", width=20)
    stats.add_column("", width=12)
    stats.add_row("[dim]Communities:[/]", f"[{style}]{m.num_communities:,}[/]")
    stats.add_row("[dim]Largest:[/]", f"[cyan]{m.largest_community_size:,} nodes[/]")
    stats.add_row("[dim]Modularity:[/]", f"[cyan]{m.modularity_estimate:.2f}[/]")
    stats.add_row("")
    stats.add_row(f"[{style}]{status}[/]", "")

    comm = Table(show_header=True, box=box.SIMPLE, padding=(0, 1))
    comm.add_column("#", style="dim", width=3)
    comm.add_column("Size", justify="right", style="green", width=8)
    comm.add_column("Sample Types", style="cyan", ratio=1)
    for i, (_, size, labels) in enumerate(m.top_communities, 1):
        comm.add_row(str(i), f"{size:,}", labels or "mixed")

    grid.add_row(stats, comm)
    return Panel(
        grid,
        title="[bold]Communities[/]",
        subtitle="[dim]Label propagation clustering[/]",
        border_style="green",
        box=box.ROUNDED,
    )


def create_community_distribution_panel(m: GraphMetrics) -> Panel:
    """Create community size distribution panel."""
    colors = ["red", "orange1", "yellow", "green", "cyan", "blue"]
    table = create_distribution_table(m.community_size_distribution, colors)
    total = sum(m.community_size_distribution.values())
    return Panel(
        table,
        title="[bold]Community Sizes[/]",
        subtitle=f"[dim]{total:,} communities[/]",
        border_style="green",
        box=box.ROUNDED,
    )


def calculate_score(m: GraphMetrics) -> tuple[int, list[str], list[str]]:
    """Calculate overall quality score."""
    score = 50
    strengths, issues = [], []

    # Scoring rules
    if m.largest_component_ratio > 0.9:
        score += 20
        strengths.append("Highly connected graph")
    elif m.largest_component_ratio > 0.7:
        score += 10
    else:
        issues.append("Fragmented graph structure")

    if m.orphan_node_ratio > 0.1:
        score -= 15
        issues.append(f"High orphan rate ({m.orphan_node_ratio:.1%})")
    elif m.orphan_node_ratio > 0.05:
        score -= 8
        issues.append(f"Moderate orphan rate ({m.orphan_node_ratio:.1%})")
    elif m.orphan_node_ratio < 0.01:
        strengths.append("Very few orphan nodes")

    if len(m.node_labels) > 20:
        score += 10
        strengths.append(f"Rich schema ({len(m.node_labels)} node types)")
    elif len(m.node_labels) >= 5:
        score += 5
    else:
        issues.append("Limited node type variety")

    if len(m.edge_labels) > 10:
        score += 10
        strengths.append(f"Diverse relationships ({len(m.edge_labels)} types)")
    elif len(m.edge_labels) >= 3:
        score += 5
    else:
        issues.append("Limited relationship types")

    if m.avg_degree > 5:
        score += 10
        strengths.append(f"Strong connectivity ({m.avg_degree:.1f} avg degree)")
    elif m.avg_degree >= 2:
        score += 5
    else:
        issues.append("Low average connectivity")

    if m.max_degree > 1000:
        strengths.append(f"Has super-hubs (max {m.max_degree:,} connections)")

    if m.avg_clustering_coefficient > 0.3:
        score += 10
        strengths.append(f"High clustering ({m.avg_clustering_coefficient:.0%})")
    elif m.avg_clustering_coefficient > 0.1:
        score += 5
        strengths.append(f"Moderate clustering ({m.avg_clustering_coefficient:.0%})")
    elif m.avg_clustering_coefficient < 0.02:
        issues.append(f"Very low clustering ({m.avg_clustering_coefficient:.1%})")

    if m.avg_path_length <= 3:
        score += 5
        strengths.append(f"Short paths ({m.avg_path_length:.1f} avg hops)")
    elif m.avg_path_length > 6:
        issues.append(f"Long paths ({m.avg_path_length:.1f} avg hops)")

    if m.graph_resilience == "robust":
        score += 5
        strengths.append("Robust structure (low hub dependency)")
    elif m.graph_resilience == "fragile":
        score -= 5
        issues.append(f"Fragile ({m.hub_dependency_score:.0%} hub dependency)")

    if len(m.orphan_node_types) > 50:
        issues.append(f"{len(m.orphan_node_types)} underused node types")
    if len(m.orphan_edge_types) > 100:
        issues.append(f"{len(m.orphan_edge_types)} underused edge types")

    if m.num_communities > 5 and m.modularity_estimate > 0.3:
        score += 5
        strengths.append(f"Good community structure ({m.num_communities} communities)")
    elif m.num_communities == 0:
        issues.append("No community structure detected")

    return max(0, min(100, score)), strengths, issues


def create_score_panel(m: GraphMetrics) -> Panel:
    """Create quality score panel."""
    score, strengths, issues = calculate_score(m)

    if score >= 80:
        color, grade, assessment = "bold green", "A", "Excellent"
    elif score >= 70:
        color, grade, assessment = "bold cyan", "B", "Good"
    elif score >= 60:
        color, grade, assessment = "bold yellow", "C", "Fair"
    else:
        color, grade, assessment = "bold red", "D", "Needs Work"

    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("", width=20)
    table.add_row(f"[{color}]{score}/100  Grade: {grade}[/]")
    table.add_row(f"[italic]{assessment}[/]")
    table.add_row("")

    if strengths:
        table.add_row(f"[green]+ {len(strengths)} strengths[/]")
        for s in strengths[:2]:
            table.add_row(f"[dim]  {s[:24]}{'...' if len(s) > 24 else ''}[/]")
    if issues:
        table.add_row(f"[red]- {len(issues)} issues[/]")
        for i in issues[:2]:
            table.add_row(f"[dim]  {i[:24]}{'...' if len(i) > 24 else ''}[/]")

    return Panel(
        table,
        title="[bold]Score[/]",
        border_style=color.replace("bold ", ""),
        box=box.DOUBLE,
    )


# =============================================================================
# DASHBOARD RENDERING
# =============================================================================


def render_dashboard(
    m: GraphMetrics, graph_name: str, output_console: Console | None = None
) -> None:
    """Render the complete dashboard."""
    out = output_console or console
    if output_console is None:
        out.clear()

    out.print(create_header(graph_name))
    out.print()

    # Overview section
    out.print(create_section_header("OVERVIEW", "At-a-glance summary"))
    row = Table.grid(expand=True)
    row.add_column(ratio=1)
    row.add_column(ratio=1)
    row.add_column(ratio=1)
    row.add_column(ratio=1)
    row.add_row(
        create_overview_panel(m),
        create_connectivity_panel(m),
        create_degree_stats_panel(m),
        create_score_panel(m),
    )
    out.print(row)
    out.print()

    # Structure section
    out.print(create_section_header("STRUCTURE", "How the graph is organized"))
    row = Table.grid(expand=True)
    row.add_column(ratio=1)
    row.add_column(ratio=1)
    row.add_column(ratio=1)
    row.add_row(
        create_degree_distribution_panel(m),
        create_clustering_panel(m),
        create_clustering_distribution_panel(m),
    )
    out.print(row)
    out.print()
    out.print(create_hub_nodes_panel(m))
    out.print()

    # Communities section
    out.print(create_section_header("COMMUNITIES", "How nodes cluster together"))
    row = Table.grid(expand=True)
    row.add_column(ratio=2)
    row.add_column(ratio=1)
    row.add_row(create_community_panel(m), create_community_distribution_panel(m))
    out.print(row)
    out.print()

    # Navigation section
    out.print(
        create_section_header("NAVIGATION", "How easy is it to traverse the graph?")
    )
    row = Table.grid(expand=True)
    row.add_column(ratio=1)
    row.add_column(ratio=2)
    row.add_row(create_path_analysis_panel(m), create_centrality_panel(m))
    out.print(row)
    out.print()

    # Quality section
    out.print(create_section_header("QUALITY & RISKS", "Potential issues to address"))
    row = Table.grid(expand=True)
    row.add_column(ratio=1)
    row.add_column(ratio=1)
    row.add_column(ratio=1)
    row.add_row(
        create_schema_quality_panel(m),
        create_reciprocity_panel(m),
        create_resilience_panel(m),
    )
    out.print(row)
    out.print()

    # Schema section
    out.print(create_section_header("SCHEMA", "Node and relationship types"))
    row = Table.grid(expand=True)
    row.add_column(ratio=1)
    row.add_column(ratio=1)
    row.add_row(
        create_labels_panel(m.node_labels, m.total_nodes, "Node Types", "cyan", "cyan"),
        create_labels_panel(
            m.edge_labels, m.total_edges, "Relationship Types", "magenta", "magenta"
        ),
    )
    out.print(row)
    out.print()


# =============================================================================
# CLI
# =============================================================================


def parse_args():
    """Parse command-line arguments."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Graph Quality Metrics Analyzer for Kartograph",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--clustering-threshold",
        type=int,
        default=50000,
        help="Use all nodes for clustering if below this count",
    )
    parser.add_argument(
        "--path-samples",
        type=int,
        default=2000,
        help="Number of source nodes for path length analysis",
    )
    parser.add_argument(
        "--centrality-pairs",
        type=int,
        default=1000,
        help="Number of node pairs for betweenness centrality",
    )
    parser.add_argument(
        "--community-iterations",
        type=int,
        default=20,
        help="Max iterations for community detection",
    )
    parser.add_argument(
        "--pagerank-iterations",
        type=int,
        default=10,
        help="Number of PageRank power iterations",
    )
    parser.add_argument(
        "--html", type=str, metavar="FILE", help="Export dashboard to HTML file"
    )
    parser.add_argument(
        "--no-display",
        action="store_true",
        help="Don't display in terminal (useful with --html)",
    )
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()

    config = MetricsConfig(
        clustering_sample_threshold=args.clustering_threshold,
        path_sample_size=args.path_samples,
        centrality_sample_pairs=args.centrality_pairs,
        community_max_iterations=args.community_iterations,
        pagerank_iterations=args.pagerank_iterations,
    )

    graph_name = os.getenv("KARTOGRAPH_DB_GRAPH_NAME", "kartograph_graph")
    console.clear()
    console.print(
        Panel(
            f"[bold cyan]Connecting to graph:[/] [green]{graph_name}[/]",
            box=box.ROUNDED,
            border_style="blue",
        )
    )
    console.print()

    try:
        conn = get_connection()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            metrics = compute_metrics(conn, graph_name, progress, config)

        conn.close()

        if not args.no_display:
            render_dashboard(metrics, graph_name)

        if args.html:
            html_console = Console(record=True, width=120, force_terminal=True)
            render_dashboard(metrics, graph_name, output_console=html_console)
            html_console.save_html(args.html)
            console.print(f"\n[green]✓[/] Exported to [bold]{args.html}[/]")

    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled by user[/]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[bold red]Error:[/] {e}")
        import traceback

        console.print(traceback.format_exc(), style="dim red")
        sys.exit(1)


if __name__ == "__main__":
    main()
