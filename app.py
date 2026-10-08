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

st.sidebar.subheader("1. Start Location (GPS)")
st.sidebar.write("Click below to get your current location from your device:")
loc = streamlit_geolocation()

orig_lat, orig_lon = None, None
if loc and loc.get('latitude') and loc.get('longitude'):
    orig_lat = loc['latitude']
    orig_lon = loc['longitude']
    st.sidebar.success(f"GPS Acquired! Lat: {orig_lat:.4f}, Lon: {orig_lon:.4f}")
else:
    st.sidebar.info("Waiting for GPS location... (Tap the button above)")

st.sidebar.subheader("2. Destination")
dest_input = st.sidebar.text_input("Enter Destination (e.g., Grand Canal Dock)", "Grand Canal Dock")

run_routing = st.sidebar.button("Calculate Safe Route", type="primary")

if run_routing:
    if orig_lat is None or orig_lon is None:
        st.error("Please allow GPS location access in your browser or click the geolocation button first.")
    else:
        try:
            with st.spinner("Locating destination and computing bridge-safe path..."):
                dest_coords = ox.geocode(f"{dest_input}, Dublin, Ireland")
                dest_lat, dest_lon = dest_coords
                
                orig_node = ox.distance.nearest_nodes(G_safe, X=orig_lon, Y=orig_lat)
                dest_node = ox.distance.nearest_nodes(G_safe, X=dest_lon, Y=dest_lat)
                route = nx.shortest_path(G_safe, orig_node, dest_node, weight='length')
                
                route_map = folium.Map(location=[orig_lat, orig_lon], zoom_start=13, tiles="Esri.WorldStreetMap")
                route_coords = [(G_safe.nodes[node]['y'], G_safe.nodes[node]['x']) for node in route]
                
                folium.PolyLine(route_coords, color="#FF4B4B", weight=6, opacity=0.85, tooltip="Bridge-Safe Route").add_to(route_map)
                folium.Marker(route_coords[0], popup="Current GPS Location", icon=folium.Icon(color="green", icon="play")).add_to(route_map)
                folium.Marker(route_coords[-1], popup="Destination", icon=folium.Icon(color="blue", icon="stop")).add_to(route_map)
                
                st.session_state.route_map = route_map
                st.session_state.route_message = f"Route plotted safely from your GPS position! Total nodes crossed: {len(route)}"
        except Exception as e:
            st.session_state.route_map = None
            st.session_state.route_message = f"Error computing route or finding destination: {e}"

if st.session_state.route_map is not None:
    st.subheader("Generated Safe Path")
    st_folium(st.session_state.route_map, width=700, height=500, returned_objects=[])
    st.success(st.session_state.route_message)
elif st.session_state.route_message.startswith("Error"):
    st.error(st.session_state.route_message)
