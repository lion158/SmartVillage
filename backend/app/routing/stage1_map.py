import osmnx as ox
import networkx as nx
import logging

# Konfiguracja logowania
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Konfiguracja OSMnx (używamy cache, żeby przyspieszyć wielokrotne uruchomienia podczas developmentu)
ox.settings.use_cache = True
ox.settings.log_console = False

class MapGraphManager:
    """
    Klasa odpowiedzialna za pobieranie mapy z OpenStreetMap, budowanie grafu
    oraz obliczanie najkrótszych ścieżek dla systemu DRT.
    """
    
    def __init__(self, location_point: tuple, dist: int = 3000, network_type: str = 'drive'):
        """
        Inicjalizuje menedżera mapy.
        
        :param location_point: Krotka (latitude, longitude) reprezentująca centrum obszaru.
        :param dist: Promień w metrach od punktu centralnego.
        :param network_type: Typ sieci drogowej (np. 'drive' dla samochodów/busów, 'all', 'walk').
        """
        self.location_point = location_point
        self.dist = dist
        self.network_type = network_type
        self.graph = None
        self.nodes = None
        self.edges = None

    def load_graph(self):
        """
        Pobiera graf drogowy z OSMnx dla zadanego obszaru.
        W przypadku wywołań lokalnych, OSMnx zapisze dane w pamięci podręcznej (cache).
        """
        logger.info(f"Pobieranie grafu dla lokalizacji {self.location_point} w promieniu {self.dist}m...")
        # Pobieramy graf (skierowany, co odzwierciedla drogi jednokierunkowe)
        self.graph = ox.graph_from_point(
            self.location_point, 
            dist=self.dist, 
            network_type=self.network_type, 
            simplify=True
        )
        logger.info(f"Graf pobrany pomyślnie. Liczba węzłów: {len(self.graph.nodes)}, Liczba krawędzi: {len(self.graph.edges)}")
        
        # Wyciągamy GeoDataFrames dla węzłów i krawędzi (przyda się później do wizualizacji i heurystyk)
        self.nodes, self.edges = ox.graph_to_gdfs(self.graph)
        
        # Obliczamy prędkości i czasy przejazdu na krawędziach
        # Dodaje atrybut 'speed_kph' (prędkość) i 'travel_time' (czas podróży w sekundach)
        self.graph = ox.add_edge_speeds(self.graph)
        self.graph = ox.add_edge_travel_times(self.graph)
        logger.info("Dodano atrybuty prędkości i czasu przejazdu do krawędzi grafu.")

    def get_nearest_node(self, point: tuple) -> int:
        """
        Znajduje najbliższy węzeł w grafie dla danych współrzędnych geograficznych (lat, lon).
        """
        if self.graph is None:
            raise ValueError("Graf nie został załadowany. Wywołaj najpierw load_graph().")
        
        # OSMnx 1.x używa ox.distance.nearest_nodes i oczekuje (X, Y) czyli (lon, lat)
        lat, lon = point
        return ox.distance.nearest_nodes(self.graph, X=lon, Y=lat)

    def calculate_shortest_path(self, origin_point: tuple, destination_point: tuple, weight: str = 'travel_time') -> list:
        """
        Oblicza najkrótszą ścieżkę między dwoma punktami (lat, lon) bazując na wybranej wadze.
        
        :param origin_point: Punkt startowy (lat, lon).
        :param destination_point: Punkt docelowy (lat, lon).
        :param weight: Waga do optymalizacji ('travel_time' dla czasu, 'length' dla dystansu).
        :return: Lista ID węzłów reprezentująca najkrótszą ścieżkę.
        """
        orig_node = self.get_nearest_node(origin_point)
        dest_node = self.get_nearest_node(destination_point)
        
        try:
            # Używamy algorytmu Dijkstry zaimplementowanego w NetworkX
            path = nx.shortest_path(self.graph, orig_node, dest_node, weight=weight)
            return path
        except nx.NetworkXNoPath:
            logger.warning(f"Brak trasy między punktem {origin_point} a {destination_point}.")
            return None

    def get_path_travel_time(self, path: list) -> float:
        """
        Zwraca całkowity czas podróży dla danej ścieżki (listy węzłów).
        """
        if not path or len(path) < 2:
            return 0.0
            
        total_time = 0.0
        for i in range(len(path) - 1):
            u = path[i]
            v = path[i+1]
            # Bierzemy pierwszą krawędź (indeks 0) między u i v (w Multidigraph)
            edge_data = self.graph.get_edge_data(u, v)[0]
            total_time += edge_data.get('travel_time', 0.0)
            
        return total_time

    def save_map_html(self, filepath: str = 'mapa_klodzko.html', passengers: list = None, hub: tuple = None):
        """Zapisuje wizualizację grafu (krawędzi) do pliku HTML za pomocą Folium."""
        import folium
        if self.edges is None:
            raise ValueError("Graf nie został załadowany.")
        
        logger.info(f"Generowanie mapy i zapisywanie do {filepath}...")
        
        # W geopandas (od którego dziedziczy edges) można łatwo narysować interaktywną mapę
        # Konwertujemy 'name' na string by uniknąć problemów z listami w niektórych kolumnach
        edges_copy = self.edges.copy()
        edges_copy['name'] = edges_copy['name'].astype(str)
        m = edges_copy.explore(tiles="OpenStreetMap", color="#808080", weight=2, tooltip="name")
        
        # Dodajemy hub (Dworzec)
        if hub:
            folium.Marker(
                [hub[0], hub[1]], 
                tooltip="Dworzec / City Hub", 
                icon=folium.Icon(color='red', icon='info-sign')
            ).add_to(m)
            
        # Dodajemy pasażerów
        if passengers:
            for idx, pax in enumerate(passengers):
                folium.Marker(
                    [pax[0], pax[1]], 
                    tooltip=f"Pasażer {idx+1}", 
                    icon=folium.Icon(color='blue', icon='user')
                ).add_to(m)
                
        m.save(filepath)
        logger.info(f"Mapa zapisana pomyślnie. Otwórz plik {filepath} w przeglądarce.")


# === Przykładowe użycie (Mockowanie) ===
if __name__ == "__main__":
    # Kłodzko jako centrum dla naszego obszaru
    TOWN_CENTER = (50.4385, 16.6543) 
    
    manager = MapGraphManager(location_point=TOWN_CENTER, dist=10000)
    manager.load_graph()
    
    # Mockowane punkty startowe subskrybentów (Faza Offline - Etap 2)
    # Lista (latitude, longitude)
    mock_passengers = [
        (50.4430, 16.6500),
        (50.4350, 16.6600),
        (50.4400, 16.6450)
    ]
    
    # Centralny węzeł, np. dworzec Kłodzko Miasto
    city_hub = (50.4370, 16.6520)
    
    # === WIZUALIZACJA MAPY ===
    # Zapisze plik mapa_klodzko.html, który możesz otworzyć w przeglądarce!
    manager.save_map_html(passengers=mock_passengers, hub=city_hub)
    
    # Test najkrótszej ścieżki i czasu
    print("\n--- TEST: Obliczanie przykładowych tras ---")
    for idx, pax in enumerate(mock_passengers):
        path = manager.calculate_shortest_path(pax, city_hub)
        travel_time_sec = manager.get_path_travel_time(path)
        
        print(f"Pasażer {idx+1}:")
        print(f"  Trasa przez {len(path)} węzłów.")
        print(f"  Szacowany czas podróży: {travel_time_sec / 60:.2f} minut.\n")
