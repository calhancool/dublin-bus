import streamlit as st
import osmnx as ox
import networkx as nx
import folium
from streamlit_folium import st_folium
import math
from streamlit_geolocation import streamlit_geolocation
import re
import urllib.parse

# Page configuration
st.set_page_config(
    page_title="Dublin Bus Safe Router",
    page_icon="🚌",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for a clean, professional, mobile-friendly look
st.markdown("""
    <style>
    .main-header {
        font-size: 2rem;
        color: #1E3A8A;
        font-weight: 700;
        margin-bottom: 0px;
    }
    .sub-text {
        color: #4B5563;
        font-size: 1.1rem;
        margin-bottom: 20px;
    }
    .card {
        background-color: #F8FAFC;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #E2E8F0;
        margin-bottom: 20px;
    }
    .badge-safe {
        background-color: #DEF7EC;
        color: #03543F;
        padding: 6px 12px;
        border-radius: 20px;
        font-weight: bold;
        font-size: 0.9rem;
        display: inline-block;
        margin-bottom: 15px;
    }
    </style>
""", unsafe_allow_html=True)

# App Header
st.markdown('<p class="main-header">🚌 Dublin Bus Safe Navigation</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-text">Bridge-safe routing for depot transfers and test driving.</p>', unsafe_allow_html=True)

# Status Badge
st.markdown('<div class="badge-safe">🛡️ Vehicle Profile: Double-Decker (Height Threshold: 4.6m)</div>', unsafe_allow_html=True)

if "route_map" not in st.session_state:
    st.session_state.route_map = None
if "route_message" not in st.session_state:
    st.session_state.route_message = ""
if "gmaps_link" not in st.session_state:
    st.session_state.gmaps_link = ""

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

with st.spinner("Loading County Dublin road network & checking low bridges..."):
    G_safe = load_routing_graph()

POPULAR_LOCATIONS = {
    "-- Select a Depot or Landmark --": None,
    "O'Connell Street, Dublin": (53.3498, -6.2603),
    "Phibsborough Garage, Dublin": (53.3601, -6.2777),
    "Broadstone Garage, Dublin": (53.3550, -6.2730),
    "Clontarf Garage, Dublin": (53.3632, -6.2198),
    "Summerhill Garage, Dublin": (53.3532, -6.2504),
    "Donnybrook Garage, Dublin": (53.3195, -6.2291),
    "Conyngham Road Garage, Dublin": (53.3474, -6.3105),
    "Jobstown, Tallaght": (53.2774, -6.3765),
    "Grand Canal Dock, Dublin": (53.3340, -6.2430),
    "Heuston Station, Dublin": (53.3474, -6.2925),
    "Dublin Airport, Dublin": (53.4273, -6.2436),
    "Custom House, Dublin": (53.3478, -6.2512)
}

# --- MAIN INTERFACE CARD ---
with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📍 1. Start Location")
        start_mode = st.radio("Start Method", ["Use Device GPS", "Choose Preset / Custom"], label_visibility="collapsed")
        
        orig_lat, orig_lon = None, None
        
        if start_mode == "Use Device GPS":
            st.write("Tap to fetch your phone/tablet GPS:")
            loc = streamlit_geolocation()
            if loc and loc.get('latitude') and loc.get('longitude'):
                orig_lat = loc['latitude']
                orig_lon = loc['longitude']
                st.success(f"GPS Locked ({orig_lat:.4f}, {orig_lon:.4f})")
            else:
                st.info("Waiting for GPS signal...")
        else:
            start_choice = st.selectbox("Start Location", list(POPULAR_LOCATIONS.keys()), key="start_select")
            if start_choice != "-- Select a Depot or Landmark --":
                orig_lat, orig_lon = POPULAR_LOCATIONS[start_choice]
            else:
                custom_start = st.text_input("Or type custom start address", placeholder="e.g. O'Connell Street")
                if custom_start:
                    try:
                        orig_lat, orig_lon = ox.geocode(f"{custom_start}, County Dublin, Ireland")
                        st.success(f"Found: {custom_start}")
                    except Exception:
                        st.error("Location not found.")

    with col2:
        st.subheader("🎯 2. Destination")
        st.write("") 
        dest_choice = st.selectbox("Destination Location", list(POPULAR_LOCATIONS.keys()), key="dest_select")
        
        dest_lat, dest_lon = None, None
        if dest_choice != "-- Select a Depot or Landmark --":
            dest_lat, dest_lon = POPULAR_LOCATIONS[dest_choice]
        else:
            custom_dest = st.text_input("Or type custom destination", placeholder="e.g. Grand Canal Dock")
            if custom_dest:
                try:
                    dest_lat, dest_lon = ox.geocode(f"{custom_dest}, County Dublin, Ireland")
                except Exception:
                    pass

    st.markdown("---")
    
    run_routing = st.button("🚀 Calculate Bridge-Safe Route", type="primary", use_container_width=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

# --- ROUTING LOGIC ---
if run_routing:
    if orig_lat is None or orig_lon is None:
        st.error("⚠️ Please specify a valid starting point via GPS or selection.")
    elif dest_lat is None or dest_lon is None:
        st.error("⚠️ Please select or type a valid destination.")
    else:
        try:
            with st.spinner("Calculating safe path avoiding low bridges..."):
                orig_node = ox.distance.nearest_nodes(G_safe, X=orig_lon, Y=orig_lat)
                dest_node = ox.distance.nearest_nodes(G_safe, X=dest_lon, Y=dest_lat)
                route = nx.shortest_path(G_safe, orig_node, dest_node, weight='length')
                
                route_map = folium.Map(location=[orig_lat, orig_lon], zoom_start=13, tiles="Esri.WorldStreetMap")
                route_coords = [(G_safe.nodes[node]['y'], G_safe.nodes[node]['x']) for node in route]
                
                folium.PolyLine(route_coords, color="#FF4B4B", weight=6, opacity=0.85, tooltip="Bridge-Safe Route").add_to(route_map)
                folium.Marker(route_coords[0], popup="Start Point", icon=folium.Icon(color="green", icon="play")).add_to(route_map)
                folium.Marker(route_coords[-1], popup="Destination", icon=folium.Icon(color="blue", icon="stop")).add_to(route_map)
                
                # Smarter Waypoint Sampling: Filter out tight clusters to prevent Google Maps from looping
                # Only pick points spaced at least ~1.5km apart along the route
                waypoints = []
                last_lat, last_lon = orig_lat, orig_lon
                
                # Take samples along the route
                sample_step = max(1, len(route) // 15)
                for i in range(sample_step, len(route) - 1, sample_step):
                    node = route[i]
                    lat = G_safe.nodes[node]['y']
                    lon = G_safe.nodes[node]['x']
                    
                    # Calculate rough distance in meters from the last waypoint
                    dist_approx = math.sqrt((lat - last_lat)**2 + (lon - last_lon)**2) * 111000
                    if dist_approx > 1200:  # Only add waypoint if it's over 1.2km away from the previous one
                        waypoints.append(f"{lat},{lon}")
                        last_lat, last_lon = lat, lon
                
                # Keep max 5 waypoints to avoid overloading Google Maps' router
                waypoints = waypoints[:5]
                
                gmaps_url = f"https://www.google.com/maps/dir/?api=1&origin={orig_lat},{orig_lon}&destination={dest_lat},{dest_lon}"
                if waypoints:
                    gmaps_url += f"&waypoints={'|'.join(waypoints)}"
                
                st.session_state.route_map = route_map
                st.session_state.gmaps_link = gmaps_url
                st.session_state.route_message = f"Route successfully calculated! Total road segments verified: {len(route)}"
        except Exception as e:
            st.session_state.route_map = None
            st.session_state.gmaps_link = ""
            st.session_state.route_message = f"Error computing route: {e}"

# --- DISPLAY RESULTS ---
if st.session_state.route_map is not None:
    st.success(st.session_state.route_message)
    
    if st.session_state.gmaps_link:
        st.markdown(
            f"""
            <a href="{st.session_state.gmaps_link}" target="_blank">
                <button style="background-color:#10B981; color:white; padding:15px 20px; border:none; border-radius:8px; font-size:18px; font-weight:bold; cursor:pointer; width:100%; margin-bottom:15px;">
                    🚗 Open Bridge-Safe Route in Google Maps
                </button>
            </a>
            """,
            unsafe_allow_html=True
        )
        
    st.subheader("🗺️ Route Map Preview")
    st_folium(st.session_state.route_map, width=1200, height=550, returned_objects=[])

elif st.session_state.route_message.startswith("Error"):
    st.error(st.session_state.route_message)
