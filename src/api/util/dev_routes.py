"""Development utility routes.

These endpoints are for development/debugging only and should NOT be
exposed in production. Easy to remove by deleting this file and the
import in main.py.

WARNING: This file contains an embedded HTML template as a string constant.
This is EXTREMELY BAD PRACTICE and violates separation of concerns. We did
this purely as a quick-and-dirty solution to avoid container path issues.
Do NOT use this pattern in production code. The proper approach would be to:
  1. Use proper static file serving with FastAPI's StaticFiles
  2. Bundle assets properly in the container image
  3. Use a templating engine like Jinja2

We know this is bad. It's intentional tech debt for a dev-only utility.
"""

import json
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse

from infrastructure.database.connection_pool import ConnectionPool
from infrastructure.dependencies import get_age_connection_pool
from infrastructure.settings import get_database_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/util", tags=["dev-utilities"])

# Embedded HTML template for graph viewer (no external file dependency)
_VIEWER_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Kartograph Graph Viewer</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { 
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #0a0a0a; 
      color: #fff;
      overflow: hidden;
    }
    #container { width: 100vw; height: 100vh; }
    #controls {
      position: fixed;
      top: 16px;
      left: 16px;
      background: rgba(20, 20, 20, 0.95);
      padding: 16px;
      border-radius: 8px;
      z-index: 1000;
      min-width: 280px;
      box-shadow: 0 4px 20px rgba(0,0,0,0.5);
    }
    #controls h1 { font-size: 16px; margin-bottom: 12px; color: #fff; }
    #stats { font-size: 12px; color: #888; margin-top: 12px; }
    #stats span { color: #4fc3f7; font-weight: 600; }
    #search {
      width: 100%;
      padding: 8px 12px;
      border: 1px solid #444;
      border-radius: 4px;
      background: #1a1a1a;
      color: #fff;
      font-size: 13px;
      margin-bottom: 12px;
    }
    #search:focus { outline: none; border-color: #4fc3f7; }
    #loading {
      position: fixed;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      font-size: 18px;
      color: #666;
      text-align: center;
    }
    #status {
      font-size: 11px;
      color: #888;
      margin-top: 8px;
    }
    .btn {
      background: #333;
      border: none;
      color: #fff;
      padding: 6px 12px;
      border-radius: 4px;
      cursor: pointer;
      font-size: 12px;
      margin-right: 8px;
      margin-top: 8px;
    }
    .btn:hover { background: #444; }
    #metadata {
      position: fixed;
      top: 16px;
      right: 16px;
      background: rgba(20, 20, 20, 0.95);
      padding: 16px;
      border-radius: 8px;
      z-index: 1000;
      min-width: 320px;
      max-width: 400px;
      max-height: 80vh;
      overflow-y: auto;
      box-shadow: 0 4px 20px rgba(0,0,0,0.5);
      display: none;
    }
    #metadata.visible { display: block; }
    #metadata h2 { font-size: 14px; margin-bottom: 12px; color: #4fc3f7; }
    #metadata .close-btn {
      position: absolute;
      top: 8px;
      right: 8px;
      background: none;
      border: none;
      color: #888;
      font-size: 18px;
      cursor: pointer;
    }
    #metadata .close-btn:hover { color: #fff; }
    #metadata table { width: 100%; border-collapse: collapse; }
    #metadata td { 
      padding: 4px 8px; 
      font-size: 12px; 
      border-bottom: 1px solid #333;
      vertical-align: top;
    }
    #metadata td:first-child { 
      color: #888; 
      font-weight: 500;
      white-space: nowrap;
      width: 100px;
    }
    #metadata td:last-child { 
      color: #fff; 
      word-break: break-word;
    }
    #metadata .hint {
      font-size: 11px;
      color: #666;
      margin-top: 8px;
      font-style: italic;
    }
    #edgeTooltip {
      position: fixed;
      background: rgba(20, 20, 20, 0.95);
      color: #fff;
      padding: 8px 12px;
      border-radius: 6px;
      font-size: 12px;
      pointer-events: none;
      z-index: 2000;
      display: none;
      box-shadow: 0 4px 12px rgba(0,0,0,0.4);
      border: 1px solid #333;
      max-width: 300px;
    }
    #edgeTooltip.visible { display: block; }
    #edgeTooltip .edge-type {
      color: #4fc3f7;
      font-weight: 600;
      font-size: 13px;
    }
    #edgeTooltip .edge-nodes {
      color: #888;
      font-size: 11px;
      margin-top: 4px;
    }
  </style>
</head>
<body>
  <div id="container"></div>
  
  <div id="controls">
    <h1>Kartograph Graph Viewer</h1>
    <input type="text" id="search" placeholder="Search nodes...">
    <div>
      <button class="btn" id="fitView">Fit to Screen</button>
      <button class="btn" id="pausePlay">Pause</button>
    </div>
    <div id="stats">
      Nodes: <span id="nodeCount">0</span> | 
      Edges: <span id="edgeCount">0</span>
    </div>
    <div id="status"></div>
  </div>
  
  <div id="metadata">
    <button class="close-btn" id="closeMetadata">&times;</button>
    <h2 id="metadataTitle">Node Details</h2>
    <table id="metadataTable"></table>
    <div class="hint">Click a node to pin details</div>
  </div>
  
  <div id="loading">Loading graph data...</div>

  <div id="edgeTooltip">
    <div class="edge-type"></div>
    <div class="edge-nodes"></div>
  </div>

  <script type="module">
    import { Cosmograph, prepareCosmographData } from 'https://esm.sh/@cosmograph/cosmograph@2.0.1';
    
    const container = document.getElementById('container');
    const loading = document.getElementById('loading');
    const statusEl = document.getElementById('status');
    const searchInput = document.getElementById('search');
    const metadataPanel = document.getElementById('metadata');
    const metadataTitle = document.getElementById('metadataTitle');
    const metadataTable = document.getElementById('metadataTable');
    const edgeTooltip = document.getElementById('edgeTooltip');
    const edgeTooltipType = edgeTooltip.querySelector('.edge-type');
    const edgeTooltipNodes = edgeTooltip.querySelector('.edge-nodes');

    let cosmograph = null;
    let isPaused = false;
    let rawNodes = [];  // Keep raw node data for metadata lookup
    let rawEdges = [];  // Keep raw edge data
    let linksForTooltip = [];  // Links array in same order as passed to Cosmograph
    let preparedLinksRef = null;  // Reference to prepared links for index lookup
    let pinnedNodeIndex = null;  // Track pinned node for click
    let mouseX = 0;  // Track mouse position for edge tooltip
    let mouseY = 0;

    // Track mouse position globally for edge tooltip placement
    document.addEventListener('mousemove', (e) => {
      mouseX = e.clientX;
      mouseY = e.clientY;
      // Update tooltip position if visible
      if (edgeTooltip.classList.contains('visible')) {
        edgeTooltip.style.left = (mouseX + 12) + 'px';
        edgeTooltip.style.top = (mouseY + 12) + 'px';
      }
    });

    // Build a map from node ID to node data for quick lookup
    let nodeIdToData = {};

    function showEdgeTooltip(edge) {
      if (!edge) {
        edgeTooltip.classList.remove('visible');
        return;
      }

      // Get source and target node labels
      const sourceNode = nodeIdToData[edge.source];
      const targetNode = nodeIdToData[edge.target];
      const sourceLabel = sourceNode ? (sourceNode.label || sourceNode.id) : edge.source;
      const targetLabel = targetNode ? (targetNode.label || targetNode.id) : edge.target;

      edgeTooltipType.textContent = edge.edgeType || edge.type || 'unknown';
      edgeTooltipNodes.textContent = sourceLabel + ' → ' + targetLabel;

      edgeTooltip.style.left = (mouseX + 12) + 'px';
      edgeTooltip.style.top = (mouseY + 12) + 'px';
      edgeTooltip.classList.add('visible');
    }

    function hideEdgeTooltip() {
      edgeTooltip.classList.remove('visible');
    }
    
    function showMetadata(node, pinned = false) {
      if (!node) {
        if (!pinned && pinnedNodeIndex === null) {
          metadataPanel.classList.remove('visible');
        }
        return;
      }
      
      metadataTitle.textContent = node.type + ': ' + (node.label || node.id);
      
      // Build table rows for all properties
      const rows = Object.entries(node)
        .filter(([key]) => !['id'].includes(key))  // Skip internal AGE id
        .map(([key, value]) => {
          const displayValue = typeof value === 'object' ? JSON.stringify(value) : String(value);
          return '<tr><td>' + key + '</td><td>' + displayValue + '</td></tr>';
        })
        .join('');
      
      metadataTable.innerHTML = rows;
      metadataPanel.classList.add('visible');
    }
    
    function hideMetadata() {
      if (pinnedNodeIndex === null) {
        metadataPanel.classList.remove('visible');
      }
    }
    
    // Close metadata panel
    document.getElementById('closeMetadata').addEventListener('click', () => {
      pinnedNodeIndex = null;
      metadataPanel.classList.remove('visible');
    });
    
    async function initGraph(data) {
      loading.textContent = 'Preparing data...';

      rawNodes = data.nodes || [];
      rawEdges = data.edges || [];

      const nodeCount = rawNodes.length;
      const edgeCount = rawEdges.length;

      document.getElementById('nodeCount').textContent = nodeCount.toLocaleString();
      document.getElementById('edgeCount').textContent = edgeCount.toLocaleString();

      // Handle empty graph
      if (nodeCount === 0) {
        loading.textContent = 'No nodes in graph. Add some data first.';
        loading.style.display = 'block';
        statusEl.textContent = 'Empty graph';
        return;
      }

      // Build node ID lookup map for edge tooltip
      nodeIdToData = {};
      rawNodes.forEach(node => {
        nodeIdToData[node.id] = node;
      });

      // Transform data to match Cosmograph expected format
      const points = rawNodes.map(n => ({
        id: n.id,
        label: n.label || n.id,
        nodeType: n.type || 'unknown',
      }));
      
      const links = rawEdges.map(e => ({
        source: e.source,
        target: e.target,
        edgeType: e.type || 'unknown',
      }));

      // Store links for tooltip lookup (same order as passed to Cosmograph)
      linksForTooltip = links;

      // Prepare data using Cosmograph Data Kit
      const hasLinks = links.length > 0;
      const dataConfig = {
        points: {
          pointIdBy: 'id',
          pointLabelBy: 'label',
          pointColorBy: 'nodeType',
        },
        ...(hasLinks && {
          links: {
            linkSourceBy: 'source',
            linkTargetsBy: ['target'],
          },
        }),
        pointSizeBy: "degree",
        pointSizeRange: [1, 100],
      };

      statusEl.textContent = 'Preparing graph data...';

      try {
        const result = await prepareCosmographData(dataConfig, points, hasLinks ? links : undefined);

        if (!result) {
          throw new Error('Failed to prepare data');
        }

        const { points: preparedPoints, links: preparedLinks, cosmographConfig } = result;

        // Store prepared links as array for tooltip lookup (if available)
        preparedLinksRef = preparedLinks ? Array.from(preparedLinks) : [];

        loading.style.display = 'none';
        statusEl.textContent = 'Running simulation...';
        
        // Destroy existing instance if any
        if (cosmograph) {
          cosmograph.destroy();
        }
        
        // Create Cosmograph with prepared data
        cosmograph = new Cosmograph(container, {
          ...cosmographConfig,
          points: preparedPoints,
          ...(preparedLinks && { links: preparedLinks }),
          backgroundColor: '#0a0a0a',

          linkWidth: 0.5,
          linkArrows: false,
          linkColor: '#555555',
          // Link hover effects (v2.5+)
          hoveredLinkColor: '#4fc3f7',
          hoveredLinkWidthIncrease: 3,
          hoveredLinkCursor: 'pointer',
          // Point hover/focus effects
          hoveredPointRingColor: '#ffffff',
          focusedPointRingColor: '#4fc3f7',
          // Simulation parameters
          simulationGravity: 0.1,
          simulationRepulsion: 1.0,
          simulationLinkSpring: 0.5,
          simulationFriction: 0.9,
          onSimulationEnd: () => {
            statusEl.textContent = 'Layout complete';
          },
          // Show metadata on hover
          onPointMouseOver: (index) => {
            if (index !== undefined && index !== null && rawNodes[index]) {
              showMetadata(rawNodes[index], false);
            }
          },
          onPointMouseOut: () => {
            hideMetadata();
          },
          // Pin metadata on click
          onPointClick: (index) => {
            if (index !== undefined && index !== null && rawNodes[index]) {
              pinnedNodeIndex = index;
              showMetadata(rawNodes[index], true);
            }
          },
          // Edge hover - show tooltip with relationship type
          onLinkMouseOver: (linkIndex) => {
            const link = preparedLinksRef?.[linkIndex];
            if (link) {
              // Use sourceidx/targetidx for point indices
              const sourceNode = rawNodes[link.sourceidx];
              const targetNode = rawNodes[link.targetidx];

              if (sourceNode && targetNode) {
                // Find the edge type by matching source/target IDs
                const matchingLink = linksForTooltip.find(l =>
                  l.source === sourceNode.id && l.target === targetNode.id
                );
                showEdgeTooltip({
                  source: sourceNode.id,
                  target: targetNode.id,
                  edgeType: matchingLink?.edgeType || 'unknown'
                });
              }
            }
          },
          onLinkMouseOut: () => {
            hideEdgeTooltip();
          },
        });
        
      } catch (err) {
        console.error('Error preparing data:', err);
        loading.innerHTML = '<div style="color: #f87171;">Error: ' + err.message + '</div>' +
          '<div style="margin-top: 8px; font-size: 12px; color: #888;">Try refreshing (Ctrl+Shift+R)</div>';
        loading.style.display = 'block';
        statusEl.textContent = 'Error loading graph';
      }
    }
    
    // Fit view (pause first for stable view, then animate)
    document.getElementById('fitView').addEventListener('click', () => {
      if (!cosmograph) return;
      cosmograph.pause();
      isPaused = true;
      document.getElementById('pausePlay').textContent = 'Play';
      statusEl.textContent = 'Paused';
      setTimeout(() => cosmograph.fitView(500), 50);
    });
    
    // Pause/Play
    document.getElementById('pausePlay').addEventListener('click', (e) => {
      if (!cosmograph) return;
      isPaused = !isPaused;
      if (isPaused) {
        cosmograph.pause();
        e.target.textContent = 'Play';
        statusEl.textContent = 'Paused';
      } else {
        cosmograph.unpause();
        e.target.textContent = 'Pause';
        statusEl.textContent = 'Running simulation...';
      }
    });
    
    // Client-side search (works on raw data)
    searchInput.addEventListener('input', (e) => {
      if (!cosmograph) return;
      
      const query = e.target.value.toLowerCase().trim();
      if (!query) {
        cosmograph.unselectAllPoints();
        statusEl.textContent = isPaused ? 'Paused' : 'Layout complete';
        return;
      }
      
      // Search in raw nodes by label, type, domainId, name, etc.
      const matchingIndices = [];
      rawNodes.forEach((node, index) => {
        const searchFields = [
          node.label,
          node.type,
          node.domainId,
          node.name,
          node.slug,
        ].filter(Boolean).map(s => String(s).toLowerCase());
        
        if (searchFields.some(field => field.includes(query))) {
          matchingIndices.push(index);
        }
      });
      
      if (matchingIndices.length > 0) {
        cosmograph.selectPoints(matchingIndices);
        statusEl.textContent = matchingIndices.length + ' matches';
        if (matchingIndices.length === 1) {
          cosmograph.zoomToPoint(matchingIndices[0], 1000);
        }
      } else {
        cosmograph.unselectAllPoints();
        statusEl.textContent = 'No matches';
      }
    });

    // Auto-load embedded data
    const embeddedData = %%GRAPH_DATA%%;
    initGraph(embeddedData);
  </script>
</body>
</html>"""


def _parse_agtype_vertex(agtype_str: str) -> dict | None:
    """Parse AGE vertex agtype string to dict."""
    s = str(agtype_str)
    if "::vertex" in s:
        s = s.replace("::vertex", "")

    try:
        data = json.loads(s)
        props = data.get("properties", {})
        age_id = str(data.get("id"))
        domain_id = props.get("id", "")
        props_copy = {k: v for k, v in props.items() if k != "id"}

        return {
            "id": age_id,
            "domainId": domain_id,
            "label": props.get("name")
            or props.get("slug")
            or domain_id
            or data.get("label", "unknown"),
            "type": data.get("label", "unknown"),
            **props_copy,
        }
    except json.JSONDecodeError:
        return None


def _parse_agtype_edge(agtype_str: str) -> dict | None:
    """Parse AGE edge agtype string to dict."""
    s = str(agtype_str)
    if "::edge" in s:
        s = s.replace("::edge", "")

    try:
        data = json.loads(s)
        props = data.get("properties", {})
        domain_id = props.get("id", "")
        props_copy = {k: v for k, v in props.items() if k != "id"}

        return {
            "id": str(data.get("id")),
            "domainId": domain_id,
            "type": data.get("label", "unknown"),
            **props_copy,
        }
    except json.JSONDecodeError:
        return None


def _fetch_graph_data(pool: ConnectionPool, graph_name: str) -> dict:
    """Fetch all nodes and edges from the graph using raw SQL.

    Uses direct SQL queries for maximum performance with large graphs.
    Returns data in format expected by the Cosmograph viewer.
    """
    logger.info(f"Fetching graph data for graph: {graph_name}")

    conn = pool.get_connection()
    try:
        with conn.cursor() as cur:
            # Ensure AGE extension is loaded for this connection
            cur.execute("LOAD 'age';")
            cur.execute("SET search_path = ag_catalog, '$user', public;")

            # Fetch nodes - use ag_catalog.agtype_out for text conversion
            cur.execute(f"""
                SELECT ag_catalog.agtype_out(node)
                FROM cypher('{graph_name}', $$ MATCH (n) RETURN n $$) AS (node agtype);
            """)
            nodes = []
            for row in cur.fetchall():
                node_data = _parse_agtype_vertex(row[0])
                if node_data:
                    nodes.append(node_data)

            logger.info(f"Fetched {len(nodes)} nodes")

            # Fetch edges with source/target IDs
            cur.execute(f"""
                SELECT ag_catalog.agtype_out(source_id),
                       ag_catalog.agtype_out(target_id),
                       ag_catalog.agtype_out(edge)
                FROM cypher('{graph_name}', $$
                    MATCH (s)-[r]->(t)
                    RETURN id(s), id(t), r
                $$) AS (source_id agtype, target_id agtype, edge agtype);
            """)
            edges = []
            for row in cur.fetchall():
                source_id = str(row[0]).strip('"')
                target_id = str(row[1]).strip('"')
                edge_data = _parse_agtype_edge(row[2])
                if edge_data:
                    edge_data["source"] = source_id
                    edge_data["target"] = target_id
                    edges.append(edge_data)

            logger.info(f"Fetched {len(edges)} edges")

        return {"nodes": nodes, "edges": edges}
    except Exception as e:
        logger.exception(f"Error fetching graph data: {e}")
        raise
    finally:
        pool.return_connection(conn)


def _build_viewer_html(graph_data: dict) -> str:
    """Build the graph viewer HTML with embedded data."""
    graph_json = json.dumps(graph_data)
    return _VIEWER_TEMPLATE.replace("%%GRAPH_DATA%%", graph_json)


@router.get("/graph-viewer", response_class=HTMLResponse)
def graph_viewer(
    pool: Annotated[ConnectionPool, Depends(get_age_connection_pool)],
) -> HTMLResponse:
    """Serve interactive graph visualization with embedded data.

    Queries the graph database, embeds the data into the Cosmograph viewer,
    and returns a self-contained HTML page.

    Development utility only - no authentication required.
    """
    try:
        settings = get_database_settings()
        graph_data = _fetch_graph_data(pool, settings.graph_name)
        html_content = _build_viewer_html(graph_data)

        return HTMLResponse(
            content=html_content,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate graph viewer: {e}",
        ) from e
