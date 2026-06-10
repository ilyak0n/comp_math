from __future__ import annotations

import time
import math
from html import escape

import folium
import numpy as np
import streamlit as st
from geopy.exc import GeocoderServiceError, GeocoderTimedOut, GeocoderUnavailable
from geopy.geocoders import Nominatim
from streamlit_folium import st_folium

from graph_utils import (
    load_graph,
    build_weight_matrices,
    compute_distance_matrix,
    tsp_bruteforce,
    tsp_greedy,
    reconstruct_full_route,
    recompute_comfort_matrix,
)

APP_TITLE = "RouteOptima - Построение оптимальных маршрутов"
COUNTRY_CODES = "ru"
DEFAULT_CENTER = [55.751244, 37.618423]
DEFAULT_ZOOM = 12
POINT_ZOOM = 16
SEARCH_LIMIT = 5
NOMINATIM_DELAY_SECONDS = 1.1
DEFAULT_FIXED_RADIUS_METERS = 2000
TSP_MAX_BRUTEFORCE = 10
RADIUS_BUFFER_FACTOR = 1.5
MIN_AUTO_RADIUS = 500


@st.cache_resource
def get_geolocator() -> Nominatim:
    return Nominatim(user_agent="courier_route_planner")


def search_address(query: str) -> tuple[list[dict], str | None]:
    geolocator = get_geolocator()
    try:
        time.sleep(NOMINATIM_DELAY_SECONDS)
        locations = geolocator.geocode(
            query,
            exactly_one=False,
            limit=SEARCH_LIMIT,
            country_codes=COUNTRY_CODES,
            language="ru",
            addressdetails=True,
            timeout=10,
        )
    except (GeocoderTimedOut, GeocoderServiceError, GeocoderUnavailable) as error:
        return [], str(error)
    if not locations:
        return [], None
    results = []
    for loc in locations:
        results.append({
            "address": loc.address,
            "lat": float(loc.latitude),
            "lon": float(loc.longitude),
        })
    return results, None


def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def compute_required_radius(points):
    if len(points) < 2:
        return MIN_AUTO_RADIUS
    max_dist = 0.0
    for i in range(len(points)):
        for j in range(i + 1, len(points)):
            d = haversine_distance(points[i]["lat"], points[i]["lon"],
                                   points[j]["lat"], points[j]["lon"])
            if d > max_dist:
                max_dist = d
    required = max_dist * RADIUS_BUFFER_FACTOR
    return max(required, MIN_AUTO_RADIUS)


@st.cache_resource(ttl=24 * 3600)
def load_graph_and_matrices(center_lat: float, center_lon: float, radius_m: int):
    G_wgs84, G_proj, node_to_idx, idx_to_node = load_graph(center_lat, center_lon, radius_m)
    matrices, _, _ = build_weight_matrices(G_proj)
    return G_wgs84, G_proj, matrices, node_to_idx, idx_to_node


def update_comfort_matrix(G_proj, custom_factors):
    comfort_matrix, _, _ = recompute_comfort_matrix(G_proj, custom_factors)
    return comfort_matrix


def clear_route() -> None:
    st.session_state.route = None


def rebuild_route() -> None:
    if len(st.session_state.points) < 2:
        st.warning("Добавьте хотя бы 2 точки")
        return

    center_lat = st.session_state.points[0]["lat"]
    center_lon = st.session_state.points[0]["lon"]

    if st.session_state.auto_radius:
        if len(st.session_state.points) >= 2:
            radius = int(compute_required_radius(st.session_state.points))
        else:
            radius = MIN_AUTO_RADIUS
        radius_mode = f"авто ({radius / 1000:.1f} км)"
    else:
        radius = st.session_state.custom_radius
        radius_mode = f"фиксированный ({radius / 1000:.1f} км)"

    current_graph_data = st.session_state.graph_data
    current_params = st.session_state.get("graph_params")
    need_reload = False
    if current_graph_data is None or current_params is None:
        need_reload = True
    elif current_params.get("center_lat") != center_lat or current_params.get("center_lon") != center_lon:
        need_reload = True
    elif current_params.get("radius") != radius:
        need_reload = True

    if need_reload:
        with st.spinner(f"Загрузка дорожной сети (радиус {radius / 1000:.1f} км)..."):
            try:
                graph_data = load_graph_and_matrices(center_lat, center_lon, radius)
                st.session_state.graph_data = graph_data
                st.session_state.graph_params = {
                    "center_lat": center_lat,
                    "center_lon": center_lon,
                    "radius": radius,
                }
                st.success("Граф загружен!")
            except Exception as e:
                st.error(f"Ошибка загрузки графа: {e}")
                return
    else:
        graph_data = current_graph_data

    G_wgs84, G_proj, matrices, node_to_idx, idx_to_node = graph_data
    criterion = st.session_state.criterion

    if criterion == "distance":
        A = matrices["distance"]
    elif criterion == "time":
        A = matrices["time"]
    elif criterion == "comfort":
        A = update_comfort_matrix(G_proj, st.session_state.custom_factors)
    else:
        st.error("Неизвестный критерий")
        return

    point_indices = []
    for pt in st.session_state.points:
        node = None
        min_dist = float("inf")
        for n, data in G_wgs84.nodes(data=True):
            lat = data.get('y')
            lon = data.get('x')
            if lat is None or lon is None:
                continue
            dist = (lat - pt["lat"]) ** 2 + (lon - pt["lon"]) ** 2
            if dist < min_dist:
                min_dist = dist
                node = n
        if node is None:
            st.error(f"Не удалось найти вершину графа для точки {pt['address']}")
            return
        point_indices.append(node_to_idx[node])

    st.session_state.point_indices = point_indices

    dist_matrix, pred_matrix = compute_distance_matrix(A, point_indices)
    if np.any(np.isinf(dist_matrix)):
        st.error("Некоторые точки недостижимы друг из друга. Увеличьте радиус графа или выберите другие точки.")
        return

    N = len(point_indices)
    method = "полный перебор" if N <= TSP_MAX_BRUTEFORCE else "жадный алгоритм"
    return_to_start = st.session_state.get("return_to_start", True)

    if return_to_start:
        if N <= TSP_MAX_BRUTEFORCE:
            tour, total_weight = tsp_bruteforce(dist_matrix, start_index=0)
        else:
            tour, total_weight = tsp_greedy(dist_matrix, start_index=0)
    else:
        if N <= TSP_MAX_BRUTEFORCE:
            import itertools
            other = list(range(1, N))
            best_weight = np.inf
            best_perm = None
            for perm in itertools.permutations(other):
                total = 0.0
                current = 0
                for nxt in perm:
                    total += dist_matrix[current, nxt]
                    current = nxt
                if total < best_weight:
                    best_weight = total
                    best_perm = perm
            if best_perm is None:
                st.error("Не удалось построить маршрут без возврата")
                return
            tour = [0] + list(best_perm)
            total_weight = best_weight
        else:
            visited = [False] * N
            tour = [0]
            visited[0] = True
            current = 0
            total_weight = 0.0
            for _ in range(N - 1):
                best = None
                best_dist = np.inf
                for j in range(N):
                    if not visited[j]:
                        d = dist_matrix[current, j]
                        if d < best_dist:
                            best_dist = d
                            best = j
                if best is None:
                    break
                total_weight += best_dist
                tour.append(best)
                visited[best] = True
                current = best

    full_route_nodes = reconstruct_full_route(tour, point_indices, pred_matrix, idx_to_node)
    dist_matrix_meters, _ = compute_distance_matrix(matrices["distance"], point_indices)
    total_length_m = 0.0
    for k in range(len(tour) - 1):
        total_length_m += dist_matrix_meters[tour[k], tour[k + 1]]

    if criterion == "time":
        total_seconds = total_weight
    else:
        time_matrix = matrices["time"]
        dist_time, _ = compute_distance_matrix(time_matrix, point_indices)
        total_seconds = 0.0
        for k in range(len(tour) - 1):
            total_seconds += dist_time[tour[k], tour[k + 1]]

    st.session_state.route = {
        "full_route_nodes": full_route_nodes,
        "tour_indices": tour,
        "total_length_m": total_length_m,
        "total_comfort": total_weight if criterion == "comfort" else None,
        "total_time_sec": total_seconds,
        "criterion": criterion,
        "method": method,
        "radius_km": radius / 1000,
        "radius_mode": radius_mode,
        "return_to_start": return_to_start,
    }
    st.success("Маршрут построен!")


def create_map_with_route():
    points = st.session_state.points
    route = st.session_state.route
    graph_data = st.session_state.graph_data

    if st.session_state.get("map_center") and st.session_state.map_center is not None:
        center = st.session_state.map_center
        zoom = st.session_state.get("map_zoom", POINT_ZOOM)
        st.session_state.map_center = None
    elif points:
        center = [points[0]["lat"], points[0]["lon"]]
        zoom = POINT_ZOOM
    else:
        center = DEFAULT_CENTER
        zoom = DEFAULT_ZOOM

    m = folium.Map(
        location=center,
        zoom_start=zoom,
        tiles="CartoDB positron",
        control_scale=True,
        attribution_control=False,
    )

    for i, pt in enumerate(points):
        number = i + 1
        color = "red" if i == 0 else "blue"
        icon_html = f"""
            <div style="
                background-color: {color};
                border-radius: 50%;
                width: 30px;
                height: 30px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-weight: bold;
                font-size: 16px;
                color: white;
                border: 2px solid white;
                box-shadow: 0 2px 5px rgba(0,0,0,0.3);
            ">{number}</div>
        """
        icon = folium.DivIcon(html=icon_html, icon_size=(30, 30), icon_anchor=(15, 15))
        popup = f"<b>{'Стартовая точка' if i == 0 else f'Точка {i + 1}'}</b><br>{escape(pt['address'])}<br>{pt['lat']:.5f}, {pt['lon']:.5f}"
        folium.Marker(
            [pt["lat"], pt["lon"]],
            popup=folium.Popup(popup, max_width=300),
            tooltip=f"{'Старт' if i == 0 else f'Точка {i + 1}'}",
            icon=icon
        ).add_to(m)

    if route and route["full_route_nodes"] and graph_data is not None:
        G_wgs84 = graph_data[0]
        coords = []
        for node_id in route["full_route_nodes"]:
            if node_id in G_wgs84.nodes:
                coords.append((G_wgs84.nodes[node_id]["y"], G_wgs84.nodes[node_id]["x"]))
        if coords:
            folium.PolyLine(coords, color="red", weight=4, opacity=0.8, tooltip="Маршрут").add_to(m)

    return m


def init_session_state() -> None:
    if "points" not in st.session_state:
        st.session_state.points = []
    if "route" not in st.session_state:
        st.session_state.route = None
    if "custom_factors" not in st.session_state:
        st.session_state.custom_factors = {
            "motorway": 0.7, "trunk": 0.8, "primary": 0.85,
            "secondary": 0.9, "tertiary": 1.0, "residential": 1.2,
            "living_street": 1.4, "service": 1.5, "unclassified": 1.3,
        }
    if "graph_data" not in st.session_state:
        st.session_state.graph_data = None
    if "graph_params" not in st.session_state:
        st.session_state.graph_params = None
    if "criterion" not in st.session_state:
        st.session_state.criterion = "distance"
    if "return_to_start" not in st.session_state:
        st.session_state.return_to_start = True
    if "search_results" not in st.session_state:
        st.session_state.search_results = []
    if "auto_radius" not in st.session_state:
        st.session_state.auto_radius = True
    if "custom_radius" not in st.session_state:
        st.session_state.custom_radius = DEFAULT_FIXED_RADIUS_METERS
    if "map_center" not in st.session_state:
        st.session_state.map_center = None
    if "map_zoom" not in st.session_state:
        st.session_state.map_zoom = POINT_ZOOM


def main():
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    init_session_state()
    st.title(APP_TITLE)

    left_col, right_col = st.columns([0.4, 0.6], gap="large")

    with left_col:
        st.subheader("Добавление точки")
        with st.form("search_form"):
            address_query = st.text_input("Введите адрес", placeholder="Например: Невский пр. 1, Санкт-Петербург")
            search_submitted = st.form_submit_button("Найти")
        if search_submitted and address_query:
            with st.spinner("Поиск..."):
                results, error = search_address(address_query)
            if error:
                st.error(f"Ошибка: {error}")
            elif not results:
                st.info("Ничего не найдено.")
            else:
                st.session_state.search_results = results

        if st.session_state.search_results:
            st.subheader("Результаты поиска")
            for idx, res in enumerate(st.session_state.search_results):
                col1, col2 = st.columns([0.8, 0.2])
                col1.write(f"{res['address']} ({res['lat']:.5f}, {res['lon']:.5f})")
                if col2.button("➕ Добавить", key=f"add_{idx}"):
                    st.session_state.points.append(res)
                    st.session_state.map_center = [res["lat"], res["lon"]]
                    st.session_state.map_zoom = POINT_ZOOM
                    clear_route()
                    if len(st.session_state.points) == 1:
                        st.session_state.graph_data = None
                        st.session_state.graph_params = None
                    st.rerun()

        st.divider()
        st.subheader("Точки маршрута")
        if not st.session_state.points:
            st.caption("Пока нет добавленных точек. Используйте поиск, чтобы добавить стартовую точку и адреса.")
        else:
            for i, pt in enumerate(st.session_state.points):
                col1, col2 = st.columns([0.8, 0.2])
                if i == 0:
                    label = f"🏁 {pt['address']}"
                else:
                    label = f"{i}. {pt['address']}"
                col1.write(label)
                if col2.button("🗑️ Удалить", key=f"del_{i}"):
                    st.session_state.points.pop(i)
                    if i == 0 and st.session_state.points:
                        st.session_state.graph_data = None
                        st.session_state.graph_params = None
                    clear_route()
                    st.rerun()
            if st.button("🗑️ Очистить все точки"):
                st.session_state.points = []
                st.session_state.graph_data = None
                st.session_state.graph_params = None
                clear_route()
                st.rerun()

        st.divider()
        st.subheader("Параметры маршрута")

        criterion = st.radio(
            "Критерий оптимизации",
            options=["distance", "time", "comfort"],
            format_func=lambda x: {"distance": "Расстояние (м)", "time": "Время (с)", "comfort": "Комфорт"}[x],
            horizontal=True,
            key="criterion_radio",
            on_change=clear_route,
        )
        st.session_state.criterion = criterion

        auto_radius = st.checkbox(
            "Автоматически рассчитать радиус по точкам",
            value=st.session_state.auto_radius,
            help="Если включено, радиус охвата графа будет автоматически вычислен на основе максимального расстояния между точками (с запасом). Иначе можно задать вручную.",
            on_change=clear_route,
            key="auto_radius_checkbox"
        )
        st.session_state.auto_radius = auto_radius

        if not auto_radius:
            custom_radius_m = st.number_input(
                "Радиус загрузки графа (метры)",
                min_value=100,
                max_value=10000,
                value=st.session_state.custom_radius,
                step=100,
                help="Задайте радиус в метрах вокруг стартовой точки для загрузки дорожной сети.",
                on_change=clear_route,
                key="custom_radius_input"
            )
            st.session_state.custom_radius = int(custom_radius_m)

        return_to_start = st.checkbox(
            "Вернуться в стартовую точку",
            value=st.session_state.return_to_start,
            help="Если отмечено, маршрут заканчивается в стартовой точке. Иначе — в последней точке доставки.",
            on_change=clear_route,
            key="return_checkbox"
        )
        st.session_state.return_to_start = return_to_start

        if criterion == "comfort":
            st.subheader("Коэффициенты комфорта")
            road_names_ru = {
                "motorway": "Автомагистраль",
                "trunk": "Скоростная дорога",
                "primary": "Главная дорога",
                "secondary": "Второстепенная дорога",
                "tertiary": "Местная дорога",
                "residential": "Жилая улица",
                "living_street": "Жилая зона",
                "service": "Служебная дорога",
                "unclassified": "Неклассифицированная",
            }
            cols = st.columns(2)
            with st.form("comfort_factors_form"):
                custom = {}
                for idx, (hw, ru_name) in enumerate(road_names_ru.items()):
                    col = cols[idx % 2]
                    default_val = st.session_state.custom_factors.get(hw, 1.0)
                    val = col.number_input(
                        f"{ru_name} ({hw})",
                        min_value=0.1,
                        max_value=5.0,
                        value=default_val,
                        step=0.05,
                        format="%.2f",
                        key=f"factor_{hw}"
                    )
                    custom[hw] = val
                if st.form_submit_button("Применить коэффициенты"):
                    st.session_state.custom_factors = custom
                    clear_route()
                    st.success("Коэффициенты обновлены. Перестройте маршрут.")

        if st.button("🚚 Построить маршрут", type="primary"):
            rebuild_route()

    with right_col:
        st.subheader("Карта")
        m = create_map_with_route()
        st_folium(m, height=550, use_container_width=True, returned_objects=[])

        if st.session_state.route:
            st.divider()
            st.markdown("### 📋 Описание маршрута")
            r = st.session_state.route
            col1, col2 = st.columns(2)
            if r["total_length_m"] is not None:
                col1.metric("🚗 Длина", f"{r['total_length_m'] / 1000:.2f} км")
            else:
                col1.metric("🚗 Длина", "—")
            if r["total_time_sec"] is not None:
                minutes = r["total_time_sec"] / 60
                col2.metric("⏱️ Время", f"{minutes:.1f} мин")
            else:
                col2.metric("⏱️ Время", "—")
            st.caption(f"**Метод:** {r['method']}")
            st.caption(f"**Радиус графа:** {r.get('radius_mode', '—')}")

            if r.get("tour_indices"):
                st.markdown("**Порядок точек:**")
                points_list = st.session_state.points
                for idx in r["tour_indices"]:
                    if idx < len(points_list):
                        addr = points_list[idx]["address"]
                        st.write(f"{idx + 1}. {addr}")


if __name__ == "__main__":
    main()
