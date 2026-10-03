import logging
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
from stage1_map import MapGraphManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DRTOfflineRouter:
    """
    Silnik optymalizacji Fazy Offline (Batch).
    Wykorzystuje Google OR-Tools do przydzielania zaplanowanych pasażerów do busów
    oraz wyznaczania najszybszych tras zjazdowych do węzła centralnego.
    """
    
    def __init__(self, map_manager: MapGraphManager, hub: tuple, passengers: list, num_vehicles: int = 2):
        self.manager = map_manager
        self.hub = hub
        self.passengers = passengers
        self.num_vehicles = num_vehicles
        # Węzły: 0 to Hub (Depot), 1 do N to pasażerowie
        self.locations = [self.hub] + self.passengers
        self.time_matrix = []

    def build_time_matrix(self):
        """
        Buduje macierz czasów przejazdu (w sekundach) między wszystkimi punktami:
        Hubem oraz wszystkimi pasażerami w formacie wymaganych przez OR-Tools (całkowite int).
        """
        logger.info(f"Budowanie macierzy czasu przejazdu dla {len(self.locations)} punktów...")
        matrix = []
        for i, origin in enumerate(self.locations):
            row = []
            for j, dest in enumerate(self.locations):
                if i == j:
                    row.append(0)
                else:
                    path = self.manager.calculate_shortest_path(origin, dest)
                    if path:
                        # OR-Tools wymaga wartości całkowitych (int)
                        travel_time = int(self.manager.get_path_travel_time(path))
                        row.append(travel_time)
                    else:
                        # Duża kara w przypadku braku połączenia w grafie
                        row.append(999999)
            matrix.append(row)
        
        self.time_matrix = matrix
        logger.info("Macierz czasu zbudowana pomyślnie.")
        return matrix

    def solve(self):
        """
        Rozwiązuje problem VRP (Vehicle Routing Problem) używając OR-Tools.
        Zwraca słownik z trasami dla poszczególnych busów.
        """
        if not self.time_matrix:
            self.build_time_matrix()
            
        # 1. Tworzymy definicję problemu dla OR-Tools (Routing Index Manager)
        # Argumenty: liczba lokacji, liczba pojazdów, index depot (startu/końca)
        manager = pywrapcp.RoutingIndexManager(len(self.locations), self.num_vehicles, 0)

        # 2. Tworzymy główny model
        routing = pywrapcp.RoutingModel(manager)

        # 3. Definiujemy funkcję kosztu (czasu) z naszej macierzy
        def time_callback(from_index, to_index):
            # Przekształcamy wewnętrzne indeksy OR-Tools z powrotem na indeksy naszej tablicy
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            return self.time_matrix[from_node][to_node]

        transit_callback_index = routing.RegisterTransitCallback(time_callback)

        # 4. Nakazujemy algorytmowi optymalizować właśnie pod kątem tego czasu przejazdu
        routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

        # 5. Dodajemy ograniczenia czasowe (Wymiar Czasu) 
        # (Przydatne m.in. by zbalansować trasy między busami)
        routing.AddDimension(
            transit_callback_index,
            0,  # brak opóźnień na węzłach (przystankach)
            3600,  # maksymalny czas trasy jednego busa w sekundach (1 godzina)
            True,  # start from zero (wymuszamy by busy zaczynały liczyć czas od 0)
            'Time'
        )

        # 6. Konfiguracja strategii szukania rozwiązania
        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)
        
        # Opcjonalnie możemy ustawić limit czasu szukania (przydatne przy dużej liczbie pasażerów)
        search_parameters.time_limit.seconds = 5 

        # 7. Rozwiązanie!
        logger.info("Uruchamianie algorytmu OR-Tools...")
        solution = routing.SolveWithParameters(search_parameters)

        if solution:
            return self._extract_routes(manager, routing, solution)
        else:
            logger.error("Nie znaleziono rozwiązania dla obecnej konfiguracji.")
            return None

    def _extract_routes(self, manager, routing, solution):
        """
        Parsuje rozwiązanie z OR-Tools do przyjaznej struktury Pythona.
        """
        routes = {}
        total_time = 0
        
        for vehicle_id in range(self.num_vehicles):
            index = routing.Start(vehicle_id)
            route = []
            route_time = 0
            
            while not routing.IsEnd(index):
                node_index = manager.IndexToNode(index)
                route.append(node_index)
                
                previous_index = index
                index = solution.Value(routing.NextVar(index))
                # Zbieramy koszt przejścia
                route_time += routing.GetArcCostForVehicle(previous_index, index, vehicle_id)
                
            # Dodajemy depot na końcu (bus musi wrócić do huba)
            route.append(manager.IndexToNode(index))
            routes[f"Bus_{vehicle_id+1}"] = {
                "path_indexes": route,
                "time_seconds": route_time
            }
            total_time += route_time
            
        logger.info(f"Całkowity czas przejazdów floty: {total_time / 60:.2f} minut.")
        return routes


if __name__ == "__main__":
    # --- TESTOWANIE ETAPU 2 ---
    # Inicjalizujemy bazę mapy tak samo jak w Etapie 1
    TOWN_CENTER = (50.4385, 16.6543)
    city_hub = (50.4370, 16.6520)
    
    # Symulujemy nieco większą liczbę pasażerów rozrzuconych po Kłodzku dla pokazania działania 2 busów
    mock_passengers = [
        (50.4430, 16.6500), # Pax 1
        (50.4350, 16.6600), # Pax 2
        (50.4400, 16.6450), # Pax 3
        (50.4450, 16.6550), # Pax 4
        (50.4300, 16.6400), # Pax 5
        (50.4320, 16.6450)  # Pax 6
    ]
    
    map_manager = MapGraphManager(location_point=TOWN_CENTER, dist=5000) # Promień 5km
    map_manager.load_graph()
    
    # Uruchamiamy router (np. 2 busy)
    router = DRTOfflineRouter(map_manager, hub=city_hub, passengers=mock_passengers, num_vehicles=2)
    routes = router.solve()
    
    if routes:
        print("\n=== ZNALEZIONE TRASY DLA BUSÓW ===")
        for bus_name, info in routes.items():
            path_idx = info["path_indexes"]
            time_m = info["time_seconds"] / 60
            
            # Tłumaczymy indeksy na czytelne punkty
            path_str = []
            for idx in path_idx:
                if idx == 0:
                    path_str.append("Hub")
                else:
                    path_str.append(f"Pax {idx}")
                    
            print(f"[{bus_name}] Czas trasy: {time_m:.2f} min. Kolejność: {' -> '.join(path_str)}")
