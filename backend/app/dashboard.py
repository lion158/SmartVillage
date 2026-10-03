import streamlit as st
import streamlit.components.v1 as components
import os
import sys

sys.path.append(os.path.dirname(__file__))
from routing.stage1_map import MapGraphManager
from routing.stage2_offline import DRTOfflineRouter

st.set_page_config(page_title="Village City DRT", layout="wide")
st.title("🚐 Village City - Transport Na Żądanie (Wirtualne Przystanki)")
st.markdown("Symulacja inteligentnego transportu dzielonego z systemem przesiadkowym i grupowaniem.")

def get_morning_requests():
    return [
        # Zamiast losowych lasów, precyzyjne domy wzdłuż głównej drogi w Żelaźnie!
        {"pickup": (50.3710, 16.6900), "dropoff": (50.4350, 16.6560), "pax": 3, "req_time": "07:30", "type": "arrival", "name": "Żelazno (Dom 1)"},
        {"pickup": (50.3750, 16.6850), "dropoff": (50.4350, 16.6560), "pax": 2, "req_time": "07:30", "type": "arrival", "name": "Żelazno (Dom 2)"},
        {"pickup": (50.3790, 16.6790), "dropoff": (50.4350, 16.6560), "pax": 4, "req_time": "07:30", "type": "arrival", "name": "Żelazno (Dom 3)"},
        {"pickup": (50.3830, 16.6730), "dropoff": (50.4350, 16.6560), "pax": 2, "req_time": "07:45", "type": "arrival", "name": "Żelazno (Dom 4)"},
        {"pickup": (50.3870, 16.6660), "dropoff": (50.4350, 16.6560), "pax": 4, "req_time": "07:45", "type": "arrival", "name": "Żelazno (Dom 5)"},
        
        # Krosnowice (Domy przy głównej drodze)
        {"pickup": (50.3920, 16.6430), "dropoff": (50.3023, 16.6565), "pax": 2, "req_time": "08:00", "type": "arrival", "name": "Krosnowice (Dom A)"},
        {"pickup": (50.3950, 16.6410), "dropoff": (50.3023, 16.6565), "pax": 1, "req_time": "08:00", "type": "arrival", "name": "Krosnowice (Dom B)"},
        {"pickup": (50.3980, 16.6380), "dropoff": (50.3023, 16.6565), "pax": 3, "req_time": "08:00", "type": "arrival", "name": "Krosnowice (Dom C)"},
        
        # Szalejów Dolny (Na trasie z Polanicy do Kłodzka)
        {"pickup": (50.4190, 16.5910), "dropoff": (50.4350, 16.6560), "pax": 2, "req_time": "08:15", "type": "arrival", "name": "Szalejów Dolny 1"},
        {"pickup": (50.4170, 16.5950), "dropoff": (50.4350, 16.6560), "pax": 1, "req_time": "08:15", "type": "arrival", "name": "Szalejów Dolny 2"},
    ]

def get_afternoon_requests():
    return [
        # POWROTY ze Szkół i Dworców do Domów na wsiach!
        # Z Kłodzka do Żelazna
        {"pickup": (50.4350, 16.6560), "dropoff": (50.3710, 16.6900), "pax": 3, "req_time": "14:00", "type": "departure", "name": "Powrót Kłodzko -> Żelazno 1"},
        {"pickup": (50.4350, 16.6560), "dropoff": (50.3790, 16.6790), "pax": 4, "req_time": "14:00", "type": "departure", "name": "Powrót Kłodzko -> Żelazno 3"},
        {"pickup": (50.4350, 16.6560), "dropoff": (50.3870, 16.6660), "pax": 4, "req_time": "15:00", "type": "departure", "name": "Powrót Kłodzko -> Żelazno 5"},
        
        # Z Bystrzycy do Krosnowic
        {"pickup": (50.3023, 16.6565), "dropoff": (50.3920, 16.6430), "pax": 2, "req_time": "15:30", "type": "departure", "name": "Powrót Bystrzyca -> Krosnowice A"},
        {"pickup": (50.3023, 16.6565), "dropoff": (50.3980, 16.6380), "pax": 4, "req_time": "15:30", "type": "departure", "name": "Powrót Bystrzyca -> Krosnowice C"},
        
        # Z Kłodzka do Szalejowa
        {"pickup": (50.4350, 16.6560), "dropoff": (50.4190, 16.5910), "pax": 2, "req_time": "16:00", "type": "departure", "name": "Powrót Kłodzko -> Szalejów"}
    ]

@st.cache_resource
def get_map_manager():
    TOWN_CENTER = (50.4385, 16.6543)
    manager = MapGraphManager(location_point=TOWN_CENTER, dist=14000)
    manager.load_graph()
    return manager

manager = get_map_manager()

dworzec_klodzko_miasto = (50.4350, 16.6560)
dworzec_polanica_zdroj = (50.4078, 16.5188)
dworzec_bystrzyca = (50.3023, 16.6565)

starts_coords = [dworzec_klodzko_miasto, dworzec_polanica_zdroj, dworzec_bystrzyca]
ends_coords = [dworzec_klodzko_miasto, dworzec_polanica_zdroj, dworzec_bystrzyca]

col1, col2 = st.columns([1, 3])

with col1:
    st.header("Scenariusz Dnia")
    
    pora_dnia = st.radio("Wybierz fazę symulacji:", ["Poranny Szczyt (Dowozy do Miast)", "Popołudnie (Powroty do Wsi)"])
    
    if pora_dnia == "Poranny Szczyt (Dowozy do Miast)":
        requests_list = get_morning_requests()
        start_time = "06:00"
    else:
        requests_list = get_afternoon_requests()
        start_time = "13:00"
        
    with st.expander(f"Lista Zgłoszeń ({len(requests_list)})", expanded=True):
        for i, req in enumerate(requests_list):
            st.markdown(f"**{req['name']}**\n- Trasa: `{req['pax']} os.` na godz. **{req['req_time']}**")
        
    st.markdown("---")
    
    if st.button("🚀 Symuluj tę fazę (Klastrowanie + OR-Tools)", use_container_width=True, type="primary"):
        with st.spinner("Szukanie Wirtualnych Przystanków i wyznaczanie tras..."):
            moja_flota = [
                {"id": "Autokar (Kłodzko)", "capacity": 40},
                {"id": "Sprinter (Polanica)", "capacity": 15},
                {"id": "Mały Bus (Bystrzyca)", "capacity": 9}
            ]
            
            router = DRTOfflineRouter(
                manager, 
                starts=starts_coords,
                ends=ends_coords,
                requests=requests_list, 
                fleet=moja_flota, 
                start_time=start_time
            )
            routes = router.solve()
            
            if routes:
                st.session_state.routes = routes
                map_path = os.path.join(os.path.dirname(__file__), "routing", "trasy_busow_dashboard.html")
                router.save_routes_map(routes, filepath=map_path)
                st.session_state.map_path = map_path
                st.rerun()

with col2:
    st.header("Wyznaczone Trasy i Wirtualne Przystanki")
    
    if "routes" in st.session_state:
        cols = st.columns(3)
        col_idx = 0
        for bus_name, info in st.session_state.routes.items():
            stops = info["stops"]
            cap_max = info["capacity_max"]
            
            with cols[col_idx % 3]:
                if stops > 0:
                    st.success(f"🚌 **{bus_name}**\n\nWykonał zadanie: **{stops} przystanków**")
                else:
                    st.error(f"🅿️ **{bus_name}**\n\nStoi w bazie (Brak potrzeb)")
            col_idx += 1
            
        st.markdown("---")
        
        if "map_path" in st.session_state and os.path.exists(st.session_state.map_path):
            with open(st.session_state.map_path, 'r', encoding='utf-8') as f:
                html_data = f.read()
            components.html(html_data, height=800, scrolling=True)
    else:
        st.info("👈 Wybierz porę dnia i kliknij przycisk, aby wyświetlić dedykowaną symulację!")
