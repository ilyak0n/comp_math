import itertools

import osmnx as ox
import networkx as nx
import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra


def load_graph(center_lat, center_lon, radius_meters):
    ox.settings.use_cache = True
    ox.settings.log_console = False

    G_wgs84 = ox.graph_from_point(
        (center_lat, center_lon),
        dist=radius_meters,
        network_type='drive',
        simplify=True
    )

    G_proj = ox.project_graph(G_wgs84)

    nodes = list(G_proj.nodes())
    node_to_idx = {node: i for i, node in enumerate(nodes)}
    idx_to_node = {i: node for i, node in enumerate(nodes)}

    return G_wgs84, G_proj, node_to_idx, idx_to_node


def build_weight_matrices(G_proj):
    nodes = list(G_proj.nodes())
    n = len(nodes)
    node_to_idx = {node: i for i, node in enumerate(nodes)}
    idx_to_node = {i: node for i, node in enumerate(nodes)}

    highway_speed_default = {
        'motorway': 110,
        'trunk': 90,
        'primary': 60,
        'secondary': 50,
        'tertiary': 40,
        'residential': 30,
        'living_street': 20,
        'service': 20,
        'unclassified': 30,
    }

    comfort_factor = {
        'motorway': 0.7,
        'trunk': 0.8,
        'primary': 0.85,
        'secondary': 0.9,
        'tertiary': 1.0,
        'residential': 1.2,
        'living_street': 1.4,
        'service': 1.5,
        'unclassified': 1.3,
    }

    row_dist, col_dist, data_dist = [], [], []
    row_time, col_time, data_time = [], [], []
    row_comfort, col_comfort, data_comfort = [], [], []

    for u, v, data in G_proj.edges(data=True):
        i = node_to_idx[u]
        j = node_to_idx[v]

        length = data.get('length', 0.0)
        if length <= 0:
            continue

        highway = data.get('highway', 'unclassified')
        if isinstance(highway, list):
            highway = highway[0]

        row_dist.append(i)
        col_dist.append(j)
        data_dist.append(length)

        maxspeed = data.get('maxspeed')
        speed_kmh = None
        if maxspeed is not None:
            if isinstance(maxspeed, list):
                maxspeed = maxspeed[0]
            if isinstance(maxspeed, (int, float)):
                speed_kmh = maxspeed
            elif isinstance(maxspeed, str):
                # извлекаем число из строки (например "60", "50 km/h")
                import re
                numbers = re.findall(r'\d+', maxspeed)
                if numbers:
                    speed_kmh = float(numbers[0])
        if speed_kmh is None:
            speed_kmh = highway_speed_default.get(highway, 30)

        speed_mps = speed_kmh / 3.6
        if speed_mps <= 0:
            speed_mps = 1e-6

        time_weight = length / speed_mps
        row_time.append(i)
        col_time.append(j)
        data_time.append(time_weight)

        factor = comfort_factor.get(highway, 1.0)
        comfort_weight = length * factor
        row_comfort.append(i)
        col_comfort.append(j)
        data_comfort.append(comfort_weight)

    matrices = {}
    matrices['distance'] = csr_matrix((data_dist, (row_dist, col_dist)), shape=(n, n))
    matrices['time'] = csr_matrix((data_time, (row_time, col_time)), shape=(n, n))
    matrices['comfort'] = csr_matrix((data_comfort, (row_comfort, col_comfort)), shape=(n, n))

    return matrices, node_to_idx, idx_to_node


def compute_distance_matrix(A_csr, point_indices):
    dist_matrix_full, pred_matrix_full = dijkstra(
        csgraph=A_csr,
        directed=True,
        indices=point_indices,
        return_predecessors=True,
        unweighted=False
    )

    N = len(point_indices)
    dist_matrix = np.zeros((N, N))
    for i in range(N):
        for j in range(N):
            dist_matrix[i, j] = dist_matrix_full[i, point_indices[j]]

    return dist_matrix, pred_matrix_full


def tsp_bruteforce(dist_matrix, start_index=0):
    N = dist_matrix.shape[0]
    other_indices = [i for i in range(N) if i != start_index]
    best_length = np.inf
    best_perm = None

    for perm in itertools.permutations(other_indices):
        total = 0
        current = start_index
        for next_node in perm:
            total += dist_matrix[current, next_node]
            current = next_node
        total += dist_matrix[current, start_index]

        if total < best_length:
            best_length = total
            best_perm = perm

    if best_perm is None:
        return [start_index], 0.0

    best_tour = [start_index] + list(best_perm) + [start_index]
    return best_tour, best_length


def tsp_greedy(dist_matrix, start_index=0):
    N = dist_matrix.shape[0]
    visited = [False] * N
    tour = [start_index]
    visited[start_index] = True
    current = start_index
    total_length = 0.0

    for _ in range(N - 1):
        best_next = None
        best_dist = np.inf
        for j in range(N):
            if not visited[j]:
                d = dist_matrix[current, j]
                if d < best_dist:
                    best_dist = d
                    best_next = j
        if best_next is None:
            break
        total_length += best_dist
        tour.append(best_next)
        visited[best_next] = True
        current = best_next

    total_length += dist_matrix[current, start_index]
    tour.append(start_index)

    return tour, total_length


def reconstruct_path(predecessors, start, end):
    if predecessors[end] == -9999 and start != end:
        return None
    path = [end]
    current = end
    while current != start:
        current = predecessors[current]
        if current == -9999:
            return None
        path.append(current)
    path.reverse()
    return path


def reconstruct_full_route(tsp_order, point_indices, pred_matrix, idx_to_node):
    full_route_indices = []

    for i in range(len(tsp_order) - 1):
        point_from = tsp_order[i]
        point_to = tsp_order[i + 1]

        start_idx = point_indices[point_from]
        end_idx = point_indices[point_to]

        pred_row = pred_matrix[point_from]
        path_segment = reconstruct_path(pred_row, start_idx, end_idx)

        if path_segment is None:
            print(f"Предупреждение: не удалось восстановить путь от {start_idx} до {end_idx}")
            continue

        if i == 0:
            full_route_indices.extend(path_segment)
        else:
            full_route_indices.extend(path_segment[1:])

    full_route_nodes = [idx_to_node[idx] for idx in full_route_indices]
    return full_route_nodes


def recompute_comfort_matrix(G_proj, custom_factors=None):
    default_factors = {
        'motorway': 0.7,
        'trunk': 0.8,
        'primary': 0.85,
        'secondary': 0.9,
        'tertiary': 1.0,
        'residential': 1.2,
        'living_street': 1.4,
        'service': 1.5,
        'unclassified': 1.3,
    }

    if custom_factors:
        default_factors.update(custom_factors)

    nodes = list(G_proj.nodes())
    n = len(nodes)
    node_to_idx = {node: i for i, node in enumerate(nodes)}
    idx_to_node = {i: node for i, node in enumerate(nodes)}

    row, col, data = [], [], []

    for u, v, attrs in G_proj.edges(data=True):
        length = attrs.get('length', 0.0)
        if length <= 0:
            continue

        highway = attrs.get('highway', 'unclassified')
        if isinstance(highway, list):
            highway = highway[0]

        factor = default_factors.get(highway, 1.0)
        comfort_weight = length * factor

        i = node_to_idx[u]
        j = node_to_idx[v]
        row.append(i)
        col.append(j)
        data.append(comfort_weight)

    from scipy.sparse import csr_matrix
    comfort_matrix = csr_matrix((data, (row, col)), shape=(n, n))

    return comfort_matrix, node_to_idx, idx_to_node
