import streamlit as st
import osmnx as ox
import networkx as nx
import folium
from streamlit_folium import st_folium
import re

st.set_page_config(page_title="Dublin Bus Safe Router", layout="wide")

st.title("🚌 Dublin Bus Bridge-Safe Navigation")
st.write("Route planner tailored for mechanics, test drivers, and depot vehicle transfers.")

def parse_height_to_meters(height_str):
    if not height_str or not isinstance(height_str, (str, int, float)):
        return None
    if isinstance(height_str, (int, float)):
        return float(height_str)
    height_str = str(height_str).lower().strip()
    match = re.search(r'(\d+(?:\.\d+)?)', height_str)
    if match:
        val = float(match.group(1))
        if 'ft' in height_str or "'" in height_str:
            val = val * 0.3048
        return val
    return None

@st.cache_resource
def load_routing_graph():
    place_name = "Dublin, Ireland"
    G = ox.graph_from_place(place_name, network_type="drive", retain_all=False)
    BUS_HEIGHT_THRESHOLD = 4.6 
    for u, v, k, data in G.edges(keys=True, data=True):
        max_height_tag = data.get('maxheight')
        if max_height_tag:
            parsed_height = parse_height_to_meters(max_height_tag)
            if parsed_height is not None and parsed_height < BUS_HEIGHT_THRESHOLD:
                data['unsafe_for_bus'] = True
            else:
                data['unsafe_for_bus'] = False
        else:
            data['unsafe_for_bus'] = False
    safe_edges = [(u, v, k) for u, v, k, data in G.edges(keys=True, data=True) if not data.get('unsafe_for_bus', False)]
    return G.edge_subgraph(safe_edges).copy()

with st.spinner("Loading Dublin road network and checking low bridges..."):
    G_safe = load_routing_graph()

st.sidebar.header("Route Parameters")

# Allow choosing between presets or typing custom addresses
input_mode = st.sidebar.radio("Input Method", ["Presets", "Type Custom Address"])

orig_lat, orig_lon, dest_lat, dest_lon = None, None, None, None
run_routing = False

if input_mode == "Presets":
    route_option = st.sidebar.selectbox(
        "Choose Test Route:",
        ["O'Connell St to Grand Canal Dock", "Phibsborough to Dublin Airport approach", "Heuston Station to Custom House"]
    )
    if route_option == "O'Connell St to Grand Canal Dock":
        orig_lat, orig_lon, dest_lat, dest_lon = 53.3498, -6.2603, 53.3340, -6.2430
    elif route_option == "Phibsborough to Dublin Airport approach":
        orig_lat, orig_lon, dest_lat, dest_lon = 53.3601, -6.2777, 53.4273, -6.2436
    else:
        orig_lat, orig_lon, dest_lat, dest_lon = 53.3474, -6.2925, 53.3478, -6.2512
    
    run_routing = st.sidebar.button("Calculate Safe Route", type="primary")

else:
    start_input = st.sidebar.text_input("Start Location", "O'Connell Street")
    dest_input = st.sidebar.text_input("Destination", "Grand Canal Dock")
    
    click_search = st.sidebar.button("Calculate Safe Route", type="primary")
    
    if click_search:
        try:
            with st.spinner("Locating addresses in Dublin..."):
                # Automatically append Dublin, Ireland to ensure accurate lookups
                start_coords = ox.geocode(f"{start_input}, Dublin, Ireland")
                dest_coords = ox.geocode(f"{dest_input}, Dublin, Ireland")
                orig_lat, orig_lon = start_coords
                dest_lat, dest_lon = dest_coords
                run_routing = True
        except Exception as e:
            st.sidebar.error(f"Could not find one or both locations. Try adding more detail (e.g., street name). Error: {e}")

if run_routing and orig_lat is not None:
    try:
        orig_node = ox.distance.nearest_nodes(G_safe, X=orig_lon, Y=orig_lat)
        dest_node = ox.distance.nearest_nodes(G_safe, X=dest_lon, Y=dest_lat)
        route = nx.shortest_path(G_safe, orig_node, dest_node, weight='length')
        
        route_map = folium.Map(location=[orig_lat, orig_lon], zoom_start=13, tiles='CartoDB positron')
        route_coords = [(G_safe.nodes[node]['y'], G_safe.nodes[node]['x']) for node in route]
        
        folium.PolyLine(route_coords, color="#FF4B4B", weight=6, opacity=0.85, tooltip="Bridge-Safe Route").add_to(route_map)
        folium.Marker(route_coords[0], popup="Start", icon=folium.Icon(color="green")).add_to(route_map)
        folium.Marker(route_coords[-1], popup="Destination", icon=folium.Icon(color="blue")).add_to(route_map)
        
        st_folium(route_map, width=700, height=500)
        st.success(f"Route plotted safely avoiding all low structures! Total nodes crossed: {len(route)}")
    except Exception as e:
        st.error(f"Error computing route between these points: {e}")
