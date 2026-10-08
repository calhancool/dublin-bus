import streamlit as st
import osmnx as ox
import networkx as nx
import folium
from streamlit_folium import st_folium
from streamlit_geolocation import streamlit_geolocation
import re

st.set_page_config(page_title="Dublin Bus Safe Router", layout="wide")

st.title("🚌 Dublin Bus Bridge-Safe Navigation")
st.write("Route planner tailored for mechanics, test drivers, and depot vehicle transfers.")

if "route_map" not in st.session_state:
    st.session_state.route_map = None
if "route_message" not in st.session_state:
    st.session_state.route_message = ""

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
    place_name = "County Dublin, Ireland"
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

# Popular Dublin locations and depots for instant selection or fallback typing
POPULAR_LOCATIONS = {
    "-- Select or type below --": None,
    "O'Connell Street, Dublin": (53.3498, -6.2603),
    "Phibsborough Garage, Dublin": (53.3601, -6.2777),
    "Broadstone Garage, Dublin": (53.3550, -6.2730),
    "Clontarf Garage, Dublin": (53.3632, -6.2198),
    "Summerhill Garage, Dublin": (53.3532, -6.2504),
    "Donnybrook Garage, Dublin": (53.3195, -6.2291),
    "Conyngham Road Garage, Dublin": (53.3474, -6.3105),
    "Grand Canal Dock, Dublin": (53.3340, -6.2430),
    "Heuston Station, Dublin": (53.3474, -6.2925),
    "Dublin Airport, Dublin": (53.4273, -6.2436),
    "Custom House, Dublin": (53.3478, -6.2512)
}

st.sidebar.header("Route Parameters")

# 1. Start Location
st.sidebar.subheader("1. Start Location")
start_mode = st.sidebar.radio("Start Method", ["Use Device GPS", "Select Preset / Manual Entry"])

orig_lat, orig_lon = None, None

if start_mode == "Use Device GPS":
    st.sidebar.write("Tap below to fetch your current GPS position:")
    loc = streamlit_geolocation()
    if loc and loc.get('latitude') and loc.get('longitude'):
        orig_lat = loc['latitude']
        orig_lon = loc['longitude']
        st.sidebar.success(f"GPS Active: {orig_lat:.4f}, {orig_lon:.4f}")
    else:
        st.sidebar.info("Waiting for GPS signal...")
else:
    start_choice = st.sidebar.selectbox("Choose Start Location", list(POPULAR_LOCATIONS.keys()), key="start_select")
    if start_choice != "-- Select or type below --":
        orig_lat, orig_lon = POPULAR_LOCATIONS[start_choice]
    else:
        custom_start = st.sidebar.text_input("Or type custom start address", "")
        if custom_start:
            try:
                coords = ox.geocode(f"{custom_start}, Dublin, Ireland")
                orig_lat, orig_lon = coords
                st.sidebar.success(f"Found: {custom_start}")
            except Exception:
                st.sidebar.error("Could not find address. Try adding more detail.")

# 2. Destination
st.sidebar.subheader("2. Destination")
dest_choice = st.sidebar.selectbox("Choose Destination", list(POPULAR_LOCATIONS.keys()), key="dest_select")

dest_lat, dest_lon = None, None
if dest_choice != "-- Select or type below --":
    dest_lat, dest_lon = POPULAR_LOCATIONS[dest_choice]
else:
    custom_dest = st.sidebar.text_input("Or type custom destination address", "Grand Canal Dock")
    if custom_dest:
        try:
            coords = ox.geocode(f"{custom_dest}, Dublin, Ireland")
            dest_lat, dest_lon = coords
        except Exception:
            pass

run_routing = st.sidebar.button("Calculate Safe Route", type="primary")

if run_routing:
    if orig_lat is None or orig_lon is None:
        st.error("Please provide a valid starting location (via GPS or selection).")
    elif dest_lat is None or dest_lon is None:
        st.error("Please select or type a valid destination.")
    else:
        try:
            with st.spinner("Computing bridge-safe route..."):
                orig_node = ox.distance.nearest_nodes(G_safe, X=orig_lon, Y=orig_lat)
                dest_node = ox.distance.nearest_nodes(G_safe, X=dest_lon, Y=dest_lat)
                route = nx.shortest_path(G_safe, orig_node, dest_node, weight='length')
                
                route_map = folium.Map(location=[orig_lat, orig_lon], zoom_start=13, tiles="Esri.WorldStreetMap")
                route_coords = [(G_safe.nodes[node]['y'], G_safe.nodes[node]['x']) for node in route]
                
                folium.PolyLine(route_coords, color="#FF4B4B", weight=6, opacity=0.85, tooltip="Bridge-Safe Route").add_to(route_map)
                folium.Marker(route_coords[0], popup="Start Point", icon=folium.Icon(color="green", icon="play")).add_to(route_map)
                folium.Marker(route_coords[-1], popup="Destination", icon=folium.Icon(color="blue", icon="stop")).add_to(route_map)
                
                st.session_state.route_map = route_map
                st.session_state.route_message = f"Route successfully plotted avoiding all low structures! Total nodes crossed: {len(route)}"
        except Exception as e:
            st.session_state.route_map = None
            st.session_state.route_message = f"Error computing route: {e}"

if st.session_state.route_map is not None:
    st.subheader("Generated Safe Path")
    st_folium(st.session_state.route_map, width=700, height=500, returned_objects=[])
    st.success(st.session_state.route_message)
elif st.session_state.route_message.startswith("Error"):
    st.error(st.session_state.route_message)
