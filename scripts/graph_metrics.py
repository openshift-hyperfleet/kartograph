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

import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

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


@dataclass
class MetricsConfig:
    """Configuration for graph metrics computation thresholds."""

    # Clustering coefficient
    clustering_sample_threshold: int = 50000  # Use all nodes if below this
    clustering_hub_sample: int = 500  # Top N hubs to always include
    clustering_random_sample: int = 9500  # Random nodes to sample

    # Path length analysis
    path_sample_size: int = 2000  # Number of source nodes for BFS
    path_hub_sample: int = 200  # Top N hubs to always include
    path_max_depth: int = 10  # Maximum BFS depth

    # Centrality
    centrality_sample_pairs: int = 1000  # Number of node pairs for betweenness
    centrality_max_depth: int = 8  # Maximum BFS depth for betweenness
    pagerank_iterations: int = 10  # Power iteration count

    # Community detection
    community_max_iterations: int = 20  # Label propagation iterations

    # Reciprocity
    reciprocity_sample_size: int = 1000  # Nodes to sample for reciprocity

    # Results
    top_hubs_count: int = 15  # Number of top hubs to track
    top_centrality_count: int = 10  # Number of top centrality nodes
    top_communities_count: int = 5  # Number of top communities to show


# Default configuration
DEFAULT_CONFIG = MetricsConfig()


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
    avg_path_length: float  # Average shortest path (sampled)
    diameter_estimate: int  # Longest shortest path found (sampled)
    path_length_distribution: dict[str, int]  # Distribution of path lengths

    # Centrality scores
    top_betweenness_nodes: list[tuple[str, str, float]]  # (slug, label, score)
    top_pagerank_nodes: list[tuple[str, str, float]]  # (slug, label, score)

    # Schema quality
    orphan_node_types: list[str]  # Node types with only 1-2 instances
    orphan_edge_types: list[str]  # Edge types with only 1-2 instances
    type_imbalance_score: float  # Gini coefficient of type distribution

    # Reciprocity analysis
    reciprocity_score: float  # Overall reciprocity (0-1)
    unbalanced_relationships: list[
        tuple[str, str, int, int]
    ]  # (type1, type2, count1, count2)

    # Hub dependency
    hub_dependency_score: float  # What % of edges go through top 5 hubs
    graph_resilience: str  # "fragile", "moderate", "robust"

    # Community detection
    num_communities: int  # Number of detected communities
    largest_community_size: int  # Size of largest community
    community_size_distribution: dict[str, int]  # Distribution of community sizes
    modularity_estimate: float  # Estimate of modularity score
    top_communities: list[tuple[int, int, str]]  # (community_id, size, sample_labels)


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


def get_all_vertex_labels(conn, graph_name: str) -> list[tuple[str, str]]:
    """Get all vertex label names and their table names."""
    query = """
    SELECT l.name, l.relation::regclass::text as table_name
    FROM ag_catalog.ag_label l
    JOIN ag_catalog.ag_graph g ON l.graph = g.graphid
    WHERE g.name = %s AND l.kind = 'v' AND l.name != '_ag_label_vertex'
    """
    return execute_sql(conn, query, (graph_name,))


def get_all_edge_labels(conn, graph_name: str) -> list[tuple[str, str]]:
    """Get all edge label names and their table names."""
    query = """
    SELECT l.name, l.relation::regclass::text as table_name
    FROM ag_catalog.ag_label l
    JOIN ag_catalog.ag_graph g ON l.graph = g.graphid
    WHERE g.name = %s AND l.kind = 'e' AND l.name != '_ag_label_edge'
    """
    return execute_sql(conn, query, (graph_name,))


def compute_metrics(
    conn, graph_name: str, progress: Progress, config: MetricsConfig = DEFAULT_CONFIG
) -> GraphMetrics:
    """Compute all graph metrics using direct SQL queries."""

    # Task: Get labels
    task1 = progress.add_task("[cyan]Discovering schema...", total=2)

    vertex_labels = get_all_vertex_labels(conn, graph_name)
    conn.commit()
    progress.advance(task1)

    edge_labels_info = get_all_edge_labels(conn, graph_name)
    conn.commit()
    progress.advance(task1)

    # Task: Count nodes
    task2 = progress.add_task("[green]Counting nodes...", total=len(vertex_labels))
    node_labels = {}
    total_nodes = 0

    for label_name, table_name in vertex_labels:
        count_result = execute_sql(
            conn, f"SELECT COUNT(*) FROM {table_name}", commit=True
        )
        count = count_result[0][0]
        node_labels[label_name] = count
        total_nodes += count
        progress.advance(task2)

    node_labels = dict(sorted(node_labels.items(), key=lambda x: -x[1]))

    # Task: Count edges
    task3 = progress.add_task("[yellow]Counting edges...", total=len(edge_labels_info))
    edge_labels = {}
    total_edges = 0

    for label_name, table_name in edge_labels_info:
        count_result = execute_sql(
            conn, f"SELECT COUNT(*) FROM {table_name}", commit=True
        )
        count = count_result[0][0]
        edge_labels[label_name] = count
        total_edges += count
        progress.advance(task3)

    edge_labels = dict(sorted(edge_labels.items(), key=lambda x: -x[1]))

    # Task: Compute degrees
    task4 = progress.add_task(
        "[magenta]Computing degrees...",
        total=len(vertex_labels) + len(edge_labels_info) * 2,
    )

    node_degrees = defaultdict(int)
    node_info = {}

    for label_name, table_name in vertex_labels:
        node_results = execute_sql(
            conn, f"SELECT id, properties FROM {table_name}", commit=True
        )
        for node_id, props in node_results:
            node_info[node_id] = (label_name, props)
            node_degrees[node_id] = 0
        progress.advance(task4)

    for edge_label, table_name in edge_labels_info:
        out_results = execute_sql(
            conn,
            f"SELECT start_id, COUNT(*) FROM {table_name} GROUP BY start_id",
            commit=True,
        )
        for node_id, count in out_results:
            node_degrees[node_id] += count
        progress.advance(task4)

        in_results = execute_sql(
            conn,
            f"SELECT end_id, COUNT(*) FROM {table_name} GROUP BY end_id",
            commit=True,
        )
        for node_id, count in in_results:
            node_degrees[node_id] += count
        progress.advance(task4)

    degrees = list(node_degrees.values())
    degree_with_info = [
        (
            nid,
            node_info.get(nid, ("unknown", {}))[0],
            node_info.get(nid, ("unknown", {}))[1],
            deg,
        )
        for nid, deg in node_degrees.items()
    ]

    # Calculate statistics
    if degrees:
        avg_degree = sum(degrees) / len(degrees)
        min_degree = min(degrees)
        max_degree = max(degrees)
        sorted_degrees = sorted(degrees)
        median_degree = sorted_degrees[len(sorted_degrees) // 2]
        variance = sum((d - avg_degree) ** 2 for d in degrees) / len(degrees)
        degree_std_dev = variance**0.5
    else:
        avg_degree = min_degree = max_degree = median_degree = degree_std_dev = 0

    orphan_nodes = sum(1 for d in degrees if d == 0)
    orphan_ratio = orphan_nodes / total_nodes if total_nodes > 0 else 0

    # Degree distribution
    degree_buckets = {
        "0": 0,
        "1": 0,
        "2-5": 0,
        "6-10": 0,
        "11-50": 0,
        "51-100": 0,
        "100+": 0,
    }
    for d in degrees:
        if d == 0:
            degree_buckets["0"] += 1
        elif d == 1:
            degree_buckets["1"] += 1
        elif d <= 5:
            degree_buckets["2-5"] += 1
        elif d <= 10:
            degree_buckets["6-10"] += 1
        elif d <= 50:
            degree_buckets["11-50"] += 1
        elif d <= 100:
            degree_buckets["51-100"] += 1
        else:
            degree_buckets["100+"] += 1

    # Edge density
    possible_edges = total_nodes * (total_nodes - 1) if total_nodes > 1 else 1
    edge_density = total_edges / possible_edges

    # Top hubs
    sorted_by_degree = sorted(degree_with_info, key=lambda x: -x[3])[
        : config.top_hubs_count
    ]
    top_hubs = []
    for node_id, label, props, degree in sorted_by_degree:
        try:
            props_str = str(props)
            readable_name = None
            if '"slug":' in props_str:
                match = re.search(r'"slug":\s*"([^"]+)"', props_str)
                if match:
                    readable_name = match.group(1)
            if not readable_name and '"id":' in props_str:
                match = re.search(r'"id":\s*"([^"]+)"', props_str)
                if match:
                    readable_name = match.group(1)
            if not readable_name:
                readable_name = str(node_id)
        except Exception:
            readable_name = str(node_id)
        top_hubs.append((readable_name, label, degree))

    # Connectedness estimation
    if orphan_ratio < 0.05 and avg_degree >= 2:
        estimated_components = 1 + orphan_nodes
        largest_component_size = total_nodes - orphan_nodes
        largest_component_ratio = (
            largest_component_size / total_nodes if total_nodes > 0 else 0
        )
    else:
        connected_nodes = total_nodes - orphan_nodes
        largest_component_size = connected_nodes
        largest_component_ratio = (
            connected_nodes / total_nodes if total_nodes > 0 else 0
        )
        estimated_components = max(1, orphan_nodes + 1)

    # Clustering coefficient calculation
    # For each node, CC = (actual edges between neighbors) / (possible edges between neighbors)
    # We use sampling for large graphs to keep computation tractable
    task5 = progress.add_task("[blue]Computing clustering...", total=100)

    # Build adjacency set for efficient neighbor lookup
    # We treat the graph as undirected for clustering coefficient
    adjacency: dict[int, set[int]] = defaultdict(set)

    for edge_label, table_name in edge_labels_info:
        edge_results = execute_sql(
            conn, f"SELECT start_id, end_id FROM {table_name}", commit=True
        )
        for start_id, end_id in edge_results:
            adjacency[start_id].add(end_id)
            adjacency[end_id].add(start_id)

    progress.advance(task5, 20)

    # Sample nodes for clustering coefficient
    # With ~11K nodes, we can afford to sample most of them
    # Only skip nodes with degree < 2 (clustering undefined for them)
    import random

    all_node_ids = list(node_degrees.keys())

    # Filter to nodes with at least 2 neighbors (clustering is defined)
    eligible_nodes = [n for n in all_node_ids if node_degrees[n] >= 2]

    # Use all eligible nodes if below threshold, otherwise stratified sample
    if len(eligible_nodes) <= config.clustering_sample_threshold:
        sample_nodes = eligible_nodes
    else:
        # Stratified sampling: ensure we include high-degree nodes
        sorted_nodes = sorted(
            eligible_nodes, key=lambda n: node_degrees[n], reverse=True
        )
        top_nodes = sorted_nodes[: config.clustering_hub_sample]
        remaining = sorted_nodes[config.clustering_hub_sample :]
        random_sample = random.sample(
            remaining, min(config.clustering_random_sample, len(remaining))
        )
        sample_nodes = top_nodes + random_sample

    progress.advance(task5, 10)

    # Calculate local clustering coefficient for sampled nodes
    clustering_coefficients = []
    nodes_with_cc = 0

    step_size = max(1, len(sample_nodes) // 70)

    for i, node_id in enumerate(sample_nodes):
        neighbors = adjacency.get(node_id, set())
        k = len(neighbors)

        if k < 2:
            # Clustering coefficient is undefined for nodes with < 2 neighbors
            # We skip these in the average
            continue

        # Count edges between neighbors
        neighbor_list = list(neighbors)
        edges_between_neighbors = 0

        for j, n1 in enumerate(neighbor_list):
            for n2 in neighbor_list[j + 1 :]:
                if n2 in adjacency.get(n1, set()):
                    edges_between_neighbors += 1

        # Possible edges between k neighbors = k*(k-1)/2
        possible_edges = k * (k - 1) // 2
        cc = edges_between_neighbors / possible_edges if possible_edges > 0 else 0
        clustering_coefficients.append(cc)
        nodes_with_cc += 1

        if i % step_size == 0:
            progress.advance(task5, 1)

    # Calculate average clustering coefficient
    if clustering_coefficients:
        avg_clustering = sum(clustering_coefficients) / len(clustering_coefficients)
    else:
        avg_clustering = 0.0

    # Clustering distribution buckets
    clustering_buckets = {
        "0.0": 0,
        "0.0-0.1": 0,
        "0.1-0.3": 0,
        "0.3-0.5": 0,
        "0.5-0.7": 0,
        "0.7-1.0": 0,
        "1.0": 0,
    }

    for cc in clustering_coefficients:
        if cc == 0:
            clustering_buckets["0.0"] += 1
        elif cc < 0.1:
            clustering_buckets["0.0-0.1"] += 1
        elif cc < 0.3:
            clustering_buckets["0.1-0.3"] += 1
        elif cc < 0.5:
            clustering_buckets["0.3-0.5"] += 1
        elif cc < 0.7:
            clustering_buckets["0.5-0.7"] += 1
        elif cc < 1.0:
            clustering_buckets["0.7-1.0"] += 1
        else:
            clustering_buckets["1.0"] += 1

    # Complete the progress bar
    progress.update(task5, completed=100)

    # =========================================================================
    # PATH LENGTH ANALYSIS (sampled BFS)
    # =========================================================================
    task6 = progress.add_task("[cyan]Analyzing paths...", total=100)

    from collections import deque

    # Sample source nodes for BFS (use stratified sample)
    path_sample_count = min(config.path_sample_size, len(eligible_nodes))
    if len(eligible_nodes) > path_sample_count:
        # Mix of high-degree and random nodes
        sorted_by_deg = sorted(
            eligible_nodes, key=lambda n: node_degrees[n], reverse=True
        )
        # Take top hubs + random sample of rest
        remaining_sample = path_sample_count - config.path_hub_sample
        path_sources = sorted_by_deg[: config.path_hub_sample] + random.sample(
            sorted_by_deg[config.path_hub_sample :],
            min(remaining_sample, len(sorted_by_deg) - config.path_hub_sample),
        )
    else:
        path_sources = eligible_nodes

    all_path_lengths = []
    max_path_found = 0

    for i, source in enumerate(path_sources[:path_sample_count]):
        # BFS from source (limited depth for performance)
        visited = {source: 0}
        queue = deque([source])

        while queue:
            current = queue.popleft()
            current_dist = visited[current]

            if current_dist >= config.path_max_depth:
                continue

            for neighbor in adjacency.get(current, set()):
                if neighbor not in visited:
                    visited[neighbor] = current_dist + 1
                    queue.append(neighbor)
                    all_path_lengths.append(current_dist + 1)
                    max_path_found = max(max_path_found, current_dist + 1)

        if i % 200 == 0:
            progress.advance(task6, 5)

    if all_path_lengths:
        avg_path_length = sum(all_path_lengths) / len(all_path_lengths)
    else:
        avg_path_length = 0.0

    diameter_estimate = max_path_found

    # Path length distribution
    path_buckets = {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0, "6+": 0}
    for pl in all_path_lengths:
        if pl == 1:
            path_buckets["1"] += 1
        elif pl == 2:
            path_buckets["2"] += 1
        elif pl == 3:
            path_buckets["3"] += 1
        elif pl == 4:
            path_buckets["4"] += 1
        elif pl == 5:
            path_buckets["5"] += 1
        else:
            path_buckets["6+"] += 1

    progress.update(task6, completed=100)

    # =========================================================================
    # CENTRALITY SCORES (approximated)
    # =========================================================================
    task7 = progress.add_task("[magenta]Computing centrality...", total=100)

    # Betweenness centrality approximation (sample-based)
    # Count how often a node appears on shortest paths between sampled pairs
    betweenness_counts: dict[int, int] = defaultdict(int)

    centrality_samples = min(config.centrality_sample_pairs, len(eligible_nodes))
    sample_pairs = []
    if len(eligible_nodes) >= 2:
        for _ in range(centrality_samples):
            pair = random.sample(eligible_nodes, 2)
            sample_pairs.append((pair[0], pair[1]))

    for idx, (src, dst) in enumerate(sample_pairs):
        # BFS to find shortest path
        visited = {src: (0, None)}  # node -> (distance, parent)
        queue = deque([src])
        found = False

        while queue and not found:
            current = queue.popleft()
            if current == dst:
                found = True
                break
            current_dist = visited[current][0]
            if current_dist >= config.centrality_max_depth:
                continue
            for neighbor in adjacency.get(current, set()):
                if neighbor not in visited:
                    visited[neighbor] = (current_dist + 1, current)
                    queue.append(neighbor)

        # Trace back path and count intermediaries
        if found:
            node = dst
            while node is not None:
                parent = visited[node][1]
                if parent is not None and node != dst and node != src:
                    betweenness_counts[node] += 1
                node = parent

        if idx % 100 == 0:
            progress.advance(task7, 5)

    # Get top betweenness nodes
    sorted_betweenness = sorted(betweenness_counts.items(), key=lambda x: -x[1])[
        : config.top_centrality_count
    ]
    top_betweenness_nodes = []
    for node_id, count in sorted_betweenness:
        label, props = node_info.get(node_id, ("unknown", {}))
        slug = _extract_slug(props, node_id)
        score = count / len(sample_pairs) if sample_pairs else 0
        top_betweenness_nodes.append((slug, label, score))

    progress.update(task7, completed=60)

    # PageRank approximation (power iteration, few iterations)
    pagerank: dict[int, float] = {n: 1.0 / len(node_degrees) for n in node_degrees}
    damping = 0.85

    for _ in range(config.pagerank_iterations):
        new_pagerank: dict[int, float] = {}
        for node in node_degrees:
            rank = (1 - damping) / len(node_degrees)
            for neighbor in adjacency.get(node, set()):
                neighbor_out_degree = len(adjacency.get(neighbor, set()))
                if neighbor_out_degree > 0:
                    rank += damping * pagerank.get(neighbor, 0) / neighbor_out_degree
            new_pagerank[node] = rank
        pagerank = new_pagerank

    # Get top PageRank nodes
    sorted_pagerank = sorted(pagerank.items(), key=lambda x: -x[1])[
        : config.top_centrality_count
    ]
    top_pagerank_nodes = []
    for node_id, score in sorted_pagerank:
        label, props = node_info.get(node_id, ("unknown", {}))
        slug = _extract_slug(props, node_id)
        top_pagerank_nodes.append((slug, label, score))

    progress.update(task7, completed=100)

    # =========================================================================
    # SCHEMA QUALITY
    # =========================================================================
    task8 = progress.add_task("[yellow]Analyzing schema...", total=100)

    # Find orphan types (types with very few instances)
    orphan_node_types = [label for label, count in node_labels.items() if count <= 2]
    orphan_edge_types = [label for label, count in edge_labels.items() if count <= 2]

    # Type imbalance (Gini coefficient)
    def gini_coefficient(values: list[int]) -> float:
        if not values or sum(values) == 0:
            return 0.0
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        cumsum = 0
        for i, val in enumerate(sorted_vals):
            cumsum += (2 * (i + 1) - n - 1) * val
        return cumsum / (n * sum(sorted_vals))

    node_type_counts = list(node_labels.values())
    type_imbalance_score = gini_coefficient(node_type_counts)

    progress.update(task8, completed=50)

    # =========================================================================
    # RECIPROCITY ANALYSIS
    # =========================================================================
    # Find edge type pairs that are likely inverses (e.g., MANAGES / MANAGED_BY)
    edge_type_list = list(edge_labels.keys())
    inverse_pairs: list[tuple[str, str, int, int]] = []

    for i, t1 in enumerate(edge_type_list):
        for t2 in edge_type_list[i + 1 :]:
            # Only match clear inverse patterns:
            # Pattern 1: "X" and "X_BY" (e.g., MANAGES / MANAGED_BY)
            # Pattern 2: "X" and "XED_BY" (e.g., DOCUMENT / DOCUMENTED_BY)
            is_inverse = False

            # Normalize for comparison
            t1_norm = t1.upper().replace("_", "")
            t2_norm = t2.upper().replace("_", "")

            # Check if one is the other + "BY" suffix
            if t2_norm == t1_norm + "BY":
                is_inverse = True
            elif t1_norm == t2_norm + "BY":
                is_inverse = True
            # Check for "ED_BY" pattern (MANAGE -> MANAGED_BY)
            elif t2_norm == t1_norm + "EDBY" or t2_norm == t1_norm + "DBy":
                is_inverse = True
            elif t1_norm == t2_norm + "EDBY" or t1_norm == t2_norm + "DBY":
                is_inverse = True
            # Check explicit pattern: X and X_BY where X ends in S or ES
            elif t1.endswith("S") and t2 == t1[:-1] + "ED_BY":
                is_inverse = True
            elif t2.endswith("S") and t1 == t2[:-1] + "ED_BY":
                is_inverse = True

            if is_inverse:
                c1, c2 = edge_labels[t1], edge_labels[t2]
                diff_pct = abs(c1 - c2) / max(c1, c2, 1)
                if diff_pct > 0.05:  # More than 5% difference is notable
                    inverse_pairs.append((t1, t2, c1, c2))

    # Overall reciprocity score
    total_reciprocal_edges = 0
    total_edges_checked = 0

    for node in list(node_degrees.keys())[: config.reciprocity_sample_size]:
        for neighbor in adjacency.get(node, set()):
            total_edges_checked += 1
            if node in adjacency.get(neighbor, set()):
                total_reciprocal_edges += 1

    reciprocity_score = total_reciprocal_edges / max(total_edges_checked, 1)

    # Sort by imbalance - only show pairs with actual count differences
    unbalanced_relationships = sorted(
        inverse_pairs, key=lambda x: abs(x[2] - x[3]), reverse=True
    )[:5]

    progress.update(task8, completed=100)

    # =========================================================================
    # HUB DEPENDENCY ANALYSIS
    # =========================================================================
    task9 = progress.add_task("[red]Analyzing resilience...", total=100)

    # Calculate what % of edges involve top 5 hubs
    top_5_hub_ids = set()
    sorted_by_degree_all = sorted(node_degrees.items(), key=lambda x: -x[1])[:5]
    for node_id, _ in sorted_by_degree_all:
        top_5_hub_ids.add(node_id)

    edges_through_hubs = 0
    total_edge_count = 0

    for node, neighbors in adjacency.items():
        for neighbor in neighbors:
            total_edge_count += 1
            if node in top_5_hub_ids or neighbor in top_5_hub_ids:
                edges_through_hubs += 1

    # Each edge counted twice (undirected), so divide by 2
    hub_dependency_score = (edges_through_hubs / 2) / max(total_edges, 1)

    # Classify resilience
    if hub_dependency_score > 0.5:
        graph_resilience = "fragile"
    elif hub_dependency_score > 0.25:
        graph_resilience = "moderate"
    else:
        graph_resilience = "robust"

    progress.update(task9, completed=100)

    # =========================================================================
    # COMMUNITY DETECTION (Label Propagation)
    # =========================================================================
    task10 = progress.add_task("[green]Detecting communities...", total=100)

    # Label Propagation Algorithm:
    # 1. Each node starts with its own label (community)
    # 2. Iteratively, each node adopts the most common label among neighbors
    # 3. Continue until convergence or max iterations

    # Initialize: each node is its own community
    node_community: dict[int, int] = {n: n for n in node_degrees}

    # For efficiency, only consider connected nodes
    connected_nodes = [n for n in node_degrees if node_degrees[n] > 0]

    converged = False

    for iteration in range(config.community_max_iterations):
        if converged:
            break

        changes = 0
        # Shuffle to avoid ordering bias
        random.shuffle(connected_nodes)

        for node in connected_nodes:
            neighbors = adjacency.get(node, set())
            if not neighbors:
                continue

            # Count labels among neighbors
            label_counts: dict[int, int] = defaultdict(int)
            for neighbor in neighbors:
                label_counts[node_community[neighbor]] += 1

            # Find most common label (with tie-breaking towards smaller label for stability)
            if label_counts:
                max_count = max(label_counts.values())
                candidates = [
                    lbl for lbl, cnt in label_counts.items() if cnt == max_count
                ]
                best_label = min(candidates)  # Stable tie-break

                if node_community[node] != best_label:
                    node_community[node] = best_label
                    changes += 1

        # Update progress
        progress.advance(task10, 4)

        # Check convergence
        if changes == 0:
            converged = True

    progress.update(task10, completed=80)

    # Collect community statistics
    community_sizes: dict[int, int] = defaultdict(int)
    community_members: dict[int, list[int]] = defaultdict(list)

    for node, community in node_community.items():
        community_sizes[community] += 1
        community_members[community].append(node)

    # Filter out singleton communities (orphan nodes)
    real_communities = {c: s for c, s in community_sizes.items() if s > 1}
    num_communities = len(real_communities)

    if real_communities:
        largest_community_size = max(real_communities.values())
    else:
        largest_community_size = 0

    # Community size distribution
    community_size_buckets = {
        "2-5": 0,
        "6-20": 0,
        "21-100": 0,
        "101-500": 0,
        "501-1000": 0,
        "1000+": 0,
    }

    for size in real_communities.values():
        if size <= 5:
            community_size_buckets["2-5"] += 1
        elif size <= 20:
            community_size_buckets["6-20"] += 1
        elif size <= 100:
            community_size_buckets["21-100"] += 1
        elif size <= 500:
            community_size_buckets["101-500"] += 1
        elif size <= 1000:
            community_size_buckets["501-1000"] += 1
        else:
            community_size_buckets["1000+"] += 1

    # Get top 5 communities with sample node labels
    sorted_communities = sorted(real_communities.items(), key=lambda x: -x[1])[
        : config.top_communities_count
    ]
    top_communities = []

    for community_id, size in sorted_communities:
        # Get sample node types from this community
        members = community_members[community_id][:10]
        sample_labels = set()
        for member in members:
            label, _ = node_info.get(member, ("unknown", {}))
            sample_labels.add(label)
        sample_str = ", ".join(list(sample_labels)[:3])
        top_communities.append((community_id, size, sample_str))

    # Estimate modularity (simplified)
    # Modularity Q = (1/2m) * sum[(Aij - ki*kj/2m) * delta(ci, cj)]
    # Simplified: compare internal edges vs expected random
    total_internal_edges = 0

    for community_id, members in community_members.items():
        if len(members) < 2:
            continue
        member_set = set(members)
        for member in members:
            for neighbor in adjacency.get(member, set()):
                if neighbor in member_set:
                    total_internal_edges += 1

    # Each edge counted twice in undirected view
    total_internal_edges //= 2

    # Expected if random: sum(ki * kj) / 2m for nodes in same community
    # Simplified estimate: internal_edges / total_edges as a ratio
    if total_edges > 0:
        internal_ratio = total_internal_edges / total_edges
        # Modularity estimate: higher internal ratio = better community structure
        # Scale to 0-1 range (real modularity ranges -0.5 to 1, typically 0.3-0.7 for good structure)
        modularity_estimate = min(1.0, internal_ratio * 1.5)
    else:
        modularity_estimate = 0.0

    progress.update(task10, completed=100)

    # =========================================================================
    # BUILD RESULT
    # =========================================================================
    return GraphMetrics(
        total_nodes=total_nodes,
        total_edges=total_edges,
        node_labels=node_labels,
        edge_labels=edge_labels,
        connected_components=estimated_components,
        largest_component_size=largest_component_size,
        largest_component_ratio=largest_component_ratio,
        orphan_nodes=orphan_nodes,
        orphan_node_ratio=orphan_ratio,
        avg_degree=avg_degree,
        min_degree=min_degree,
        max_degree=max_degree,
        median_degree=median_degree,
        degree_std_dev=degree_std_dev,
        edge_density=edge_density,
        top_hub_nodes=top_hubs,
        degree_distribution=degree_buckets,
        avg_clustering_coefficient=avg_clustering,
        clustering_distribution=clustering_buckets,
        # New metrics
        avg_path_length=avg_path_length,
        diameter_estimate=diameter_estimate,
        path_length_distribution=path_buckets,
        top_betweenness_nodes=top_betweenness_nodes,
        top_pagerank_nodes=top_pagerank_nodes,
        orphan_node_types=orphan_node_types,
        orphan_edge_types=orphan_edge_types,
        type_imbalance_score=type_imbalance_score,
        reciprocity_score=reciprocity_score,
        unbalanced_relationships=unbalanced_relationships,
        hub_dependency_score=hub_dependency_score,
        graph_resilience=graph_resilience,
        # Community detection
        num_communities=num_communities,
        largest_community_size=largest_community_size,
        community_size_distribution=community_size_buckets,
        modularity_estimate=modularity_estimate,
        top_communities=top_communities,
    )


def _extract_slug(props, node_id) -> str:
    """Extract slug or id from node properties."""
    try:
        props_str = str(props)
        if '"slug":' in props_str:
            match = re.search(r'"slug":\s*"([^"]+)"', props_str)
            if match:
                return match.group(1)
        if '"id":' in props_str:
            match = re.search(r'"id":\s*"([^"]+)"', props_str)
            if match:
                return match.group(1)
    except Exception:
        pass
    return str(node_id)


def create_header(graph_name: str) -> Panel:
    """Create the header panel."""
    title = Text()
    title.append("  KARTOGRAPH  ", style="bold white on blue")
    title.append("  Graph Quality Analyzer  ", style="bold cyan")

    subtitle = Text(f"Analyzing: {graph_name}", style="dim")

    return Panel(
        Group(title, subtitle),
        box=box.DOUBLE,
        border_style="blue",
        padding=(0, 2),
    )


def create_overview_panel(metrics: GraphMetrics) -> Panel:
    """Create the overview statistics panel."""
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Metric", style="dim")
    table.add_column("Value", justify="right", style="bold")

    table.add_row("Total Nodes", f"[green]{metrics.total_nodes:,}[/]")
    table.add_row("Total Edges", f"[cyan]{metrics.total_edges:,}[/]")
    table.add_row("Node Types", f"[yellow]{len(metrics.node_labels):,}[/]")
    table.add_row("Edge Types", f"[magenta]{len(metrics.edge_labels):,}[/]")
    table.add_row("", "")
    table.add_row(
        "Edges/Node", f"[blue]{metrics.total_edges / metrics.total_nodes:.2f}[/]"
    )
    table.add_row("Avg Degree", f"[blue]{metrics.avg_degree:.2f}[/]")

    return Panel(
        table, title="[bold]Overview[/]", border_style="green", box=box.ROUNDED
    )


def create_connectivity_panel(metrics: GraphMetrics) -> Panel:
    """Create the connectivity metrics panel."""
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Metric", style="dim")
    table.add_column("Value", justify="right")

    # Color code the connectivity ratio
    ratio = metrics.largest_component_ratio
    if ratio > 0.9:
        ratio_style = "bold green"
        status = "Excellent"
    elif ratio > 0.7:
        ratio_style = "bold yellow"
        status = "Good"
    else:
        ratio_style = "bold red"
        status = "Fragmented"

    table.add_row("Connected", f"[{ratio_style}]{ratio:.1%}[/]")
    table.add_row("Status", f"[{ratio_style}]{status}[/]")
    table.add_row("", "")

    # Orphan nodes
    orphan_style = (
        "green"
        if metrics.orphan_node_ratio < 0.01
        else "yellow"
        if metrics.orphan_node_ratio < 0.05
        else "red"
    )
    table.add_row("Orphans", f"[{orphan_style}]{metrics.orphan_nodes:,}[/]")
    table.add_row("Orphan %", f"[{orphan_style}]{metrics.orphan_node_ratio:.1%}[/]")

    return Panel(
        table, title="[bold]Connectivity[/]", border_style="cyan", box=box.ROUNDED
    )


def create_degree_stats_panel(metrics: GraphMetrics) -> Panel:
    """Create the degree statistics panel."""
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Stat", style="dim")
    table.add_column("Value", justify="right", style="bold cyan")

    table.add_row("Min", str(metrics.min_degree))
    table.add_row("Median", str(int(metrics.median_degree)))
    table.add_row("Average", f"{metrics.avg_degree:.1f}")
    table.add_row("Max", f"[bold yellow]{metrics.max_degree:,}[/]")
    table.add_row("Std Dev", f"{metrics.degree_std_dev:.1f}")

    return Panel(
        table, title="[bold]Degree Stats[/]", border_style="magenta", box=box.ROUNDED
    )


def create_clustering_panel(metrics: GraphMetrics) -> Panel:
    """Create the clustering coefficient panel with intuitive explanation."""
    cc = metrics.avg_clustering_coefficient

    # Determine status with intuitive descriptions
    if cc > 0.5:
        cc_style = "bold green"
        status = "Tight-knit"
        bar_filled = 5
        description = "Related nodes form\nstrong groups"
    elif cc > 0.3:
        cc_style = "bold cyan"
        status = "Well-grouped"
        bar_filled = 4
        description = "Good community\nstructure"
    elif cc > 0.15:
        cc_style = "bold yellow"
        status = "Some clusters"
        bar_filled = 3
        description = "Partial grouping\nof related nodes"
    elif cc > 0.05:
        cc_style = "yellow"
        status = "Sparse"
        bar_filled = 2
        description = "Weak community\nstructure"
    else:
        cc_style = "red"
        status = "No clusters"
        bar_filled = 1
        description = "Nodes don't form\nnatural groups"

    # Build visual bar
    bar_empty = 5 - bar_filled

    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("", width=18)

    table.add_row(f"[{cc_style}]{cc:.0%}[/] [dim]clustered[/]")
    table.add_row("")
    table.add_row(f"[{cc_style}]{'●' * bar_filled}[/][dim]{'○' * bar_empty}[/]")
    table.add_row(f"[{cc_style}]{status}[/]")
    table.add_row("")
    table.add_row(f"[dim italic]{description.split(chr(10))[0]}[/]")
    if len(description.split("\n")) > 1:
        table.add_row(f"[dim italic]{description.split(chr(10))[1]}[/]")

    return Panel(
        table, title="[bold]Clustering[/]", border_style="blue", box=box.ROUNDED
    )


def create_clustering_distribution_panel(metrics: GraphMetrics) -> Panel:
    """Create a visual clustering distribution with intuitive labels."""
    total = sum(metrics.clustering_distribution.values())
    max_bar_width = 16

    # Header explanation
    header = Text()
    header.append("If node A connects to B and C,\n", style="dim")
    header.append("do B and C also connect?\n\n", style="dim")

    # Map technical ranges to intuitive descriptions
    # Think: "How interconnected are my neighbors?"
    friendly_labels = {
        "0.0": "None connect",  # 0% of neighbor pairs connect
        "0.0-0.1": "Almost none",
        "0.1-0.3": "Some do",
        "0.3-0.5": "About half",
        "0.5-0.7": "Most do",
        "0.7-1.0": "Nearly all",
        "1.0": "All connect",  # 100% of neighbor pairs connect
    }

    # Colors from red (none) to green (all)
    colors = ["red", "orange1", "yellow", "green_yellow", "cyan", "green", "bold green"]

    table = Table(show_header=False, box=None, padding=(0, 0), show_edge=False)
    table.add_column("Label", width=12)
    table.add_column("Bar", width=max_bar_width)
    table.add_column("Pct", justify="right", width=7)

    for i, (bucket, count) in enumerate(metrics.clustering_distribution.items()):
        pct = count / total if total > 0 else 0
        bar_width = int(pct * max_bar_width)
        color = colors[i % len(colors)]
        label = friendly_labels.get(bucket, bucket)
        bar = f"[{color}]{'█' * bar_width}[/]{'░' * (max_bar_width - bar_width)}"
        table.add_row(f"[dim]{label}[/]", bar, f"[{color}]{pct:>5.1%}[/]")

    return Panel(
        Group(header, table),
        title="[bold]Neighbor Connections[/]",
        subtitle=f"[dim]{total:,} nodes[/]",
        border_style="blue",
        box=box.ROUNDED,
    )


def create_degree_distribution_panel(metrics: GraphMetrics) -> Panel:
    """Create a visual degree distribution panel."""
    total = metrics.total_nodes
    max_bar_width = 25

    table = Table(show_header=True, box=None, padding=(0, 1))
    table.add_column("Range", style="dim", width=8)
    table.add_column("Count", justify="right", width=7)
    table.add_column("Distribution", width=max_bar_width + 8)

    colors = ["red", "yellow", "green", "cyan", "blue", "magenta", "white"]

    for i, (bucket, count) in enumerate(metrics.degree_distribution.items()):
        pct = count / total if total > 0 else 0
        bar_width = int(pct * max_bar_width)
        color = colors[i % len(colors)]
        bar = f"[{color}]{'█' * bar_width}[/]{'░' * (max_bar_width - bar_width)} {pct:>5.1%}"
        table.add_row(bucket, f"{count:,}", bar)

    return Panel(
        table,
        title="[bold]Degree Distribution[/]",
        border_style="yellow",
        box=box.ROUNDED,
    )


def create_hub_nodes_panel(metrics: GraphMetrics) -> Panel:
    """Create the top hub nodes panel."""
    table = Table(show_header=True, box=box.SIMPLE, padding=(0, 1), expand=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("Node", style="bold", ratio=2)  # Expand to fill space
    table.add_column("Type", style="cyan", ratio=1)
    table.add_column("Connections", justify="right", style="green", width=12)

    for i, (name, label, degree) in enumerate(metrics.top_hub_nodes[:10], 1):
        # Color gradient based on rank
        if i <= 3:
            rank_style = "bold yellow"
            degree_style = "bold green"
        elif i <= 6:
            rank_style = "dim"
            degree_style = "green"
        else:
            rank_style = "dim"
            degree_style = "dim green"

        table.add_row(
            f"[{rank_style}]{i}[/]", name, label, f"[{degree_style}]{degree:,}[/]"
        )

    return Panel(
        table, title="[bold]Top Hub Nodes[/]", border_style="green", box=box.ROUNDED
    )


def create_node_labels_panel(metrics: GraphMetrics) -> Panel:
    """Create the node labels distribution panel."""
    table = Table(show_header=True, box=box.SIMPLE, padding=(0, 1), expand=True)
    table.add_column("Label", style="cyan", ratio=2)
    table.add_column("Count", justify="right", style="green", width=8)
    table.add_column("%", justify="right", style="dim", width=6)

    total = metrics.total_nodes
    for label, count in list(metrics.node_labels.items())[:8]:
        pct = count / total * 100 if total > 0 else 0
        table.add_row(label, f"{count:,}", f"{pct:.1f}%")

    remaining = len(metrics.node_labels) - 8
    if remaining > 0:
        table.add_row(f"[dim]... +{remaining} more[/]", "", "")

    return Panel(
        table, title="[bold]Node Types[/]", border_style="cyan", box=box.ROUNDED
    )


def create_edge_labels_panel(metrics: GraphMetrics) -> Panel:
    """Create the edge labels distribution panel."""
    table = Table(show_header=True, box=box.SIMPLE, padding=(0, 1), expand=True)
    table.add_column("Relationship", style="magenta", ratio=2)
    table.add_column("Count", justify="right", style="green", width=8)
    table.add_column("%", justify="right", style="dim", width=6)

    total = metrics.total_edges
    for label, count in list(metrics.edge_labels.items())[:8]:
        pct = count / total * 100 if total > 0 else 0
        table.add_row(label, f"{count:,}", f"{pct:.1f}%")

    remaining = len(metrics.edge_labels) - 8
    if remaining > 0:
        table.add_row(f"[dim]... +{remaining} more[/]", "", "")

    return Panel(
        table,
        title="[bold]Relationship Types[/]",
        border_style="magenta",
        box=box.ROUNDED,
    )


def create_path_analysis_panel(metrics: GraphMetrics) -> Panel:
    """Create the path length analysis panel."""
    grid = Table.grid(padding=(0, 2))
    grid.add_column()
    grid.add_column()

    # Left side: Summary stats
    stats = Table(show_header=False, box=None, padding=(0, 1))
    stats.add_column("", width=16)
    stats.add_column("", width=10)

    apl = metrics.avg_path_length
    if apl <= 3:
        apl_style = "bold green"
        apl_status = "Excellent"
        apl_desc = "Very accessible"
    elif apl <= 5:
        apl_style = "cyan"
        apl_status = "Good"
        apl_desc = "Easy navigation"
    else:
        apl_style = "yellow"
        apl_status = "Long paths"
        apl_desc = "May need shortcuts"

    stats.add_row("[dim]Average path:[/]", f"[{apl_style}]{apl:.1f} hops[/]")
    stats.add_row("[dim]Status:[/]", f"[{apl_style}]{apl_status}[/]")
    stats.add_row("[dim]Diameter:[/]", f"[cyan]{metrics.diameter_estimate} hops[/]")
    stats.add_row("", "")
    stats.add_row(f"[dim italic]{apl_desc}[/]", "")

    # Right side: Distribution
    dist_table = Table(show_header=False, box=None, padding=(0, 0))
    dist_table.add_column("Hops", width=5, style="dim")
    dist_table.add_column("Bar", width=12)
    dist_table.add_column("%", width=5, justify="right")

    total = sum(metrics.path_length_distribution.values())
    max_bar = 10
    if total > 0:
        for dist, count in metrics.path_length_distribution.items():
            pct = count / total
            bar_width = int(pct * max_bar)
            bar = f"[cyan]{'█' * bar_width}[/]{'░' * (max_bar - bar_width)}"
            dist_table.add_row(dist, bar, f"{pct:.0%}")

    grid.add_row(stats, dist_table)

    return Panel(
        grid,
        title="[bold]Path Length[/]",
        subtitle="[dim]How many hops to reach other nodes?[/]",
        border_style="cyan",
        box=box.ROUNDED,
    )


def create_centrality_panel(metrics: GraphMetrics) -> Panel:
    """Create the centrality scores panel with side-by-side layout."""
    # Create two tables side by side
    grid = Table.grid(expand=True, padding=(0, 2))
    grid.add_column(ratio=1)
    grid.add_column(ratio=1)

    # PageRank table - no truncation, let it expand
    pr_table = Table(show_header=True, box=box.SIMPLE, padding=(0, 1), expand=True)
    pr_table.add_column("#", style="dim", width=2)
    pr_table.add_column("Node", style="cyan", ratio=2)
    pr_table.add_column("Type", style="dim", ratio=1)
    pr_table.add_column("Score", justify="right", style="magenta", width=8)

    for i, (slug, label, score) in enumerate(metrics.top_pagerank_nodes[:5], 1):
        pr_table.add_row(str(i), slug, label, f"{score:.4f}")

    # Betweenness table - no truncation
    bt_table = Table(show_header=True, box=box.SIMPLE, padding=(0, 1), expand=True)
    bt_table.add_column("#", style="dim", width=2)
    bt_table.add_column("Node", style="cyan", ratio=2)
    bt_table.add_column("Type", style="dim", ratio=1)
    bt_table.add_column("Bridge %", justify="right", style="yellow", width=8)

    for i, (slug, label, score) in enumerate(metrics.top_betweenness_nodes[:5], 1):
        bt_table.add_row(str(i), slug, label, f"{score:.0%}")

    # Wrap in panels
    pr_panel = Panel(
        pr_table,
        title="[magenta]PageRank[/] [dim](influence)[/]",
        box=box.SIMPLE,
        padding=(0, 0),
    )
    bt_panel = Panel(
        bt_table,
        title="[yellow]Betweenness[/] [dim](bridges)[/]",
        box=box.SIMPLE,
        padding=(0, 0),
    )

    grid.add_row(pr_panel, bt_panel)

    return Panel(
        grid,
        title="[bold]Centrality[/]",
        subtitle="[dim]Which nodes are most important?[/]",
        border_style="magenta",
        box=box.ROUNDED,
    )


def create_schema_quality_panel(metrics: GraphMetrics) -> Panel:
    """Create the schema quality panel."""
    table = Table(show_header=False, box=None, padding=(0, 1), expand=True)
    table.add_column("")

    # Type balance (Gini)
    gini = metrics.type_imbalance_score
    if gini < 0.5:
        gini_style = "green"
        gini_status = "Balanced"
    elif gini < 0.7:
        gini_style = "yellow"
        gini_status = "Some imbalance"
    else:
        gini_style = "red"
        gini_status = "Very imbalanced"

    table.add_row(f"[dim]Type Balance:[/] [{gini_style}]{gini_status}[/]")
    table.add_row("")

    # Orphan types
    orphan_nodes = len(metrics.orphan_node_types)
    orphan_edges = len(metrics.orphan_edge_types)

    if orphan_nodes > 0:
        table.add_row(
            f"[yellow]{orphan_nodes}[/] [dim]rare node types (used 1-2 times)[/]"
        )
    else:
        table.add_row("[green]No rare node types[/]")

    if orphan_edges > 0:
        table.add_row(
            f"[yellow]{orphan_edges}[/] [dim]rare edge types (used 1-2 times)[/]"
        )
    else:
        table.add_row("[green]No rare edge types[/]")

    return Panel(
        table,
        title="[bold]Schema Quality[/]",
        border_style="yellow",
        box=box.ROUNDED,
    )


def create_reciprocity_panel(metrics: GraphMetrics) -> Panel:
    """Create the reciprocity analysis panel."""
    table = Table(show_header=False, box=None, padding=(0, 1), expand=True)
    table.add_column("")

    # Overall reciprocity
    recip = metrics.reciprocity_score
    if recip > 0.8:
        recip_style = "green"
        recip_status = "Highly bidirectional"
    elif recip > 0.5:
        recip_style = "cyan"
        recip_status = "Mostly bidirectional"
    elif recip > 0.2:
        recip_style = "yellow"
        recip_status = "Mixed direction"
    else:
        recip_style = "dim"
        recip_status = "Mostly one-way"

    table.add_row(f"[{recip_style}]{recip:.0%}[/] [dim]of edges have a reverse edge[/]")
    table.add_row(f"[dim]{recip_status}[/]")

    # Unbalanced inverse pairs (e.g., MANAGES vs MANAGED_BY should have same count)
    if metrics.unbalanced_relationships:
        table.add_row("")
        table.add_row("[dim]Inverse pairs with mismatched counts:[/]")
        for t1, t2, c1, c2 in metrics.unbalanced_relationships[:2]:
            # Show as: MANAGES (440) vs MANAGED_BY (447)
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


def create_resilience_panel(metrics: GraphMetrics) -> Panel:
    """Create the hub dependency / resilience panel."""
    dep = metrics.hub_dependency_score
    resilience = metrics.graph_resilience

    if resilience == "robust":
        style = "bold green"
        icon = "●●●●●"
        desc = "Graph would survive hub removal"
    elif resilience == "moderate":
        style = "bold yellow"
        icon = "●●●○○"
        desc = "Some dependency on key hubs"
    else:
        style = "bold red"
        icon = "●○○○○"
        desc = "Heavy reliance on top hubs - fragile!"

    table = Table(show_header=False, box=None, padding=(0, 1), expand=True)
    table.add_column("")

    table.add_row(f"[{style}]{resilience.upper()}[/] [{style}]{icon}[/]")
    table.add_row("")
    table.add_row(f"[dim]{dep:.0%} of edges touch top 5 hubs[/]")
    table.add_row("")
    table.add_row(f"[dim italic]{desc}[/]")

    return Panel(
        table,
        title="[bold]Resilience[/]",
        subtitle="[dim]Hub dependency risk[/]",
        border_style="red" if resilience == "fragile" else "green",
        box=box.ROUNDED,
    )


def create_community_panel(metrics: GraphMetrics) -> Panel:
    """Create the community detection panel."""
    grid = Table.grid(expand=True, padding=(0, 2))
    grid.add_column(ratio=1)
    grid.add_column(ratio=1)

    # Left side: Summary stats
    stats = Table(show_header=False, box=None, padding=(0, 1))
    stats.add_column("", width=20)
    stats.add_column("", width=12)

    num_comm = metrics.num_communities
    if num_comm > 50:
        comm_style = "cyan"
        comm_status = "Many communities"
    elif num_comm > 10:
        comm_style = "green"
        comm_status = "Good structure"
    elif num_comm > 1:
        comm_style = "yellow"
        comm_status = "Few communities"
    else:
        comm_style = "red"
        comm_status = "No communities"

    stats.add_row("[dim]Communities:[/]", f"[{comm_style}]{num_comm:,}[/]")
    stats.add_row(
        "[dim]Largest:[/]", f"[cyan]{metrics.largest_community_size:,} nodes[/]"
    )
    stats.add_row("[dim]Modularity:[/]", f"[cyan]{metrics.modularity_estimate:.2f}[/]")
    stats.add_row("")
    stats.add_row(f"[{comm_style}]{comm_status}[/]", "")

    # Right side: Top communities
    comm_table = Table(show_header=True, box=box.SIMPLE, padding=(0, 1))
    comm_table.add_column("#", style="dim", width=3)
    comm_table.add_column("Size", justify="right", style="green", width=8)
    comm_table.add_column("Sample Types", style="cyan", ratio=1)

    for i, (comm_id, size, sample_labels) in enumerate(metrics.top_communities, 1):
        comm_table.add_row(str(i), f"{size:,}", sample_labels or "mixed")

    grid.add_row(stats, comm_table)

    return Panel(
        grid,
        title="[bold]Communities[/]",
        subtitle="[dim]Label propagation clustering[/]",
        border_style="green",
        box=box.ROUNDED,
    )


def create_community_distribution_panel(metrics: GraphMetrics) -> Panel:
    """Create the community size distribution panel."""
    total = sum(metrics.community_size_distribution.values())
    max_bar_width = 15

    table = Table(show_header=False, box=None, padding=(0, 0), show_edge=False)
    table.add_column("Size", width=10)
    table.add_column("Bar", width=max_bar_width)
    table.add_column("Count", justify="right", width=8)

    colors = ["red", "orange1", "yellow", "green", "cyan", "blue"]

    for i, (bucket, count) in enumerate(metrics.community_size_distribution.items()):
        if total > 0:
            pct = count / total
            bar_width = int(pct * max_bar_width)
        else:
            pct = 0
            bar_width = 0
        color = colors[i % len(colors)]
        bar = f"[{color}]{'█' * bar_width}[/]{'░' * (max_bar_width - bar_width)}"
        table.add_row(f"[dim]{bucket}[/]", bar, f"[{color}]{count:,}[/]")

    return Panel(
        table,
        title="[bold]Community Sizes[/]",
        subtitle=f"[dim]{total:,} communities[/]",
        border_style="green",
        box=box.ROUNDED,
    )


def calculate_score(metrics: GraphMetrics) -> tuple[int, list[str], list[str]]:
    """Calculate overall quality score and identify strengths/issues."""
    strengths = []
    issues = []

    score = 50  # Base score

    # Connectedness (up to 20 points)
    if metrics.largest_component_ratio > 0.9:
        score += 20
        strengths.append("Highly connected graph")
    elif metrics.largest_component_ratio > 0.7:
        score += 10
    else:
        issues.append("Fragmented graph structure")

    # Orphan rate (penalty up to 15)
    if metrics.orphan_node_ratio > 0.1:
        score -= 15
        issues.append(f"High orphan rate ({metrics.orphan_node_ratio:.1%})")
    elif metrics.orphan_node_ratio > 0.05:
        score -= 8
        issues.append(f"Moderate orphan rate ({metrics.orphan_node_ratio:.1%})")
    elif metrics.orphan_node_ratio < 0.01:
        strengths.append("Very few orphan nodes")

    # Schema richness (up to 10 points)
    if len(metrics.node_labels) > 20:
        score += 10
        strengths.append(f"Rich schema ({len(metrics.node_labels)} node types)")
    elif len(metrics.node_labels) < 5:
        issues.append("Limited node type variety")
    else:
        score += 5

    # Relationship variety (up to 10 points)
    if len(metrics.edge_labels) > 10:
        score += 10
        strengths.append(f"Diverse relationships ({len(metrics.edge_labels)} types)")
    elif len(metrics.edge_labels) < 3:
        issues.append("Limited relationship types")
    else:
        score += 5

    # Connectivity (up to 10 points)
    if metrics.avg_degree > 5:
        score += 10
        strengths.append(f"Strong connectivity ({metrics.avg_degree:.1f} avg degree)")
    elif metrics.avg_degree < 2:
        issues.append("Low average connectivity")
    else:
        score += 5

    # Super hubs
    if metrics.max_degree > 1000:
        strengths.append(f"Has super-hubs (max {metrics.max_degree:,} connections)")

    # Clustering coefficient (up to 10 points)
    cc = metrics.avg_clustering_coefficient
    if cc > 0.3:
        score += 10
        strengths.append(f"High clustering ({cc:.0%})")
    elif cc > 0.1:
        score += 5
        strengths.append(f"Moderate clustering ({cc:.0%})")
    elif cc < 0.02:
        issues.append(f"Very low clustering ({cc:.1%})")

    # Path length (up to 5 points)
    if metrics.avg_path_length <= 3:
        score += 5
        strengths.append(f"Short paths ({metrics.avg_path_length:.1f} avg hops)")
    elif metrics.avg_path_length > 6:
        issues.append(f"Long paths ({metrics.avg_path_length:.1f} avg hops)")

    # Resilience (up to 5 points)
    if metrics.graph_resilience == "robust":
        score += 5
        strengths.append("Robust structure (low hub dependency)")
    elif metrics.graph_resilience == "fragile":
        score -= 5
        issues.append(f"Fragile ({metrics.hub_dependency_score:.0%} hub dependency)")

    # Schema quality
    if len(metrics.orphan_node_types) > 50:
        issues.append(f"{len(metrics.orphan_node_types)} underused node types")
    if len(metrics.orphan_edge_types) > 100:
        issues.append(f"{len(metrics.orphan_edge_types)} underused edge types")

    # Community structure (up to 5 points)
    if metrics.num_communities > 5 and metrics.modularity_estimate > 0.3:
        score += 5
        strengths.append(
            f"Good community structure ({metrics.num_communities} communities)"
        )
    elif metrics.num_communities == 0:
        issues.append("No community structure detected")

    return max(0, min(100, int(score))), strengths, issues


def create_score_panel(metrics: GraphMetrics) -> Panel:
    """Create a compact quality score panel."""
    score, strengths, issues = calculate_score(metrics)

    # Score color
    if score >= 80:
        score_color = "bold green"
        grade = "A"
        assessment = "Excellent"
    elif score >= 70:
        score_color = "bold cyan"
        grade = "B"
        assessment = "Good"
    elif score >= 60:
        score_color = "bold yellow"
        grade = "C"
        assessment = "Fair"
    else:
        score_color = "bold red"
        grade = "D"
        assessment = "Needs Work"

    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("", width=20)

    # Score display
    table.add_row(f"[{score_color}]{score}/100  Grade: {grade}[/]")
    table.add_row(f"[italic]{assessment}[/]")
    table.add_row("")

    # Compact strengths (just count + top 2)
    if strengths:
        table.add_row(f"[green]+ {len(strengths)} strengths[/]")
        for s in strengths[:2]:
            # Truncate long strings
            s_short = s[:22] + ".." if len(s) > 24 else s
            table.add_row(f"[dim]  {s_short}[/]")

    # Compact issues
    if issues:
        table.add_row(f"[red]- {len(issues)} issues[/]")
        for i in issues[:2]:
            i_short = i[:22] + ".." if len(i) > 24 else i
            table.add_row(f"[dim]  {i_short}[/]")

    return Panel(
        table,
        title="[bold]Score[/]",
        border_style=score_color.replace("bold ", ""),
        box=box.DOUBLE,
    )


def create_section_header(title: str, subtitle: str = "") -> Panel:
    """Create a section header."""
    content = Text()
    content.append(f"  {title}  ", style="bold white on dark_blue")
    if subtitle:
        content.append(f"  {subtitle}", style="dim")
    return Panel(content, box=box.SIMPLE, padding=(0, 0), style="dim")


def render_dashboard(
    metrics: GraphMetrics,
    graph_name: str,
    output_console: Console | None = None,
) -> None:
    """Render the complete dashboard with logical groupings.

    Args:
        metrics: Computed graph metrics
        graph_name: Name of the graph being analyzed
        output_console: Console to render to (defaults to global console)
    """
    out = output_console or console

    # Only clear if rendering to terminal
    if output_console is None:
        out.clear()

    # =========================================================================
    # HEADER
    # =========================================================================
    out.print(create_header(graph_name))
    out.print()

    # =========================================================================
    # SECTION 1: OVERVIEW & SCORE
    # =========================================================================
    out.print(create_section_header("OVERVIEW", "At-a-glance summary"))

    overview_row = Table.grid(expand=True)
    overview_row.add_column(ratio=1)
    overview_row.add_column(ratio=1)
    overview_row.add_column(ratio=1)
    overview_row.add_column(ratio=1)
    overview_row.add_row(
        create_overview_panel(metrics),
        create_connectivity_panel(metrics),
        create_degree_stats_panel(metrics),
        create_score_panel(metrics),
    )
    out.print(overview_row)
    out.print()

    # =========================================================================
    # SECTION 2: GRAPH STRUCTURE
    # =========================================================================
    out.print(create_section_header("STRUCTURE", "How the graph is organized"))

    # Row 1: Distributions
    struct_row1 = Table.grid(expand=True)
    struct_row1.add_column(ratio=1)
    struct_row1.add_column(ratio=1)
    struct_row1.add_column(ratio=1)
    struct_row1.add_row(
        create_degree_distribution_panel(metrics),
        create_clustering_panel(metrics),
        create_clustering_distribution_panel(metrics),
    )
    out.print(struct_row1)
    out.print()

    # Row 2: Hub nodes
    out.print(create_hub_nodes_panel(metrics))
    out.print()

    # =========================================================================
    # SECTION 3: COMMUNITIES
    # =========================================================================
    out.print(create_section_header("COMMUNITIES", "How nodes cluster together"))

    community_row = Table.grid(expand=True)
    community_row.add_column(ratio=2)
    community_row.add_column(ratio=1)
    community_row.add_row(
        create_community_panel(metrics),
        create_community_distribution_panel(metrics),
    )
    out.print(community_row)
    out.print()

    # =========================================================================
    # SECTION 4: NAVIGATION & REACHABILITY
    # =========================================================================
    out.print(
        create_section_header("NAVIGATION", "How easy is it to traverse the graph?")
    )

    nav_row = Table.grid(expand=True)
    nav_row.add_column(ratio=1)
    nav_row.add_column(ratio=2)
    nav_row.add_row(
        create_path_analysis_panel(metrics),
        create_centrality_panel(metrics),
    )
    out.print(nav_row)
    out.print()

    # =========================================================================
    # SECTION 5: QUALITY & RISKS
    # =========================================================================
    out.print(create_section_header("QUALITY & RISKS", "Potential issues to address"))

    quality_row = Table.grid(expand=True)
    quality_row.add_column(ratio=1)
    quality_row.add_column(ratio=1)
    quality_row.add_column(ratio=1)
    quality_row.add_row(
        create_schema_quality_panel(metrics),
        create_reciprocity_panel(metrics),
        create_resilience_panel(metrics),
    )
    out.print(quality_row)
    out.print()

    # =========================================================================
    # SECTION 6: SCHEMA DETAILS
    # =========================================================================
    out.print(create_section_header("SCHEMA", "Node and relationship types"))

    schema_row = Table.grid(expand=True)
    schema_row.add_column(ratio=1)
    schema_row.add_column(ratio=1)
    schema_row.add_row(
        create_node_labels_panel(metrics),
        create_edge_labels_panel(metrics),
    )
    out.print(schema_row)
    out.print()


def parse_args():
    """Parse command-line arguments."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Graph Quality Metrics Analyzer for Kartograph",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Sampling thresholds
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

    # Output options
    parser.add_argument(
        "--html",
        type=str,
        metavar="FILE",
        help="Export dashboard to HTML file (e.g., --html report.html)",
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

    # Build config from args
    config = MetricsConfig(
        clustering_sample_threshold=args.clustering_threshold,
        path_sample_size=args.path_samples,
        centrality_sample_pairs=args.centrality_pairs,
        community_max_iterations=args.community_iterations,
        pagerank_iterations=args.pagerank_iterations,
    )

    graph_name = os.getenv("KARTOGRAPH_DB_GRAPH_NAME", "kartograph_graph")

    console.clear()

    # Show connection banner
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

        # Progress display
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            metrics = compute_metrics(conn, graph_name, progress, config)

        conn.close()

        # Render to terminal (unless --no-display)
        if not args.no_display:
            render_dashboard(metrics, graph_name)

        # Export to HTML if requested
        if args.html:
            # Create a console that records output for HTML export
            # Use a wide width for better HTML rendering
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
