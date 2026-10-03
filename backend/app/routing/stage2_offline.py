import logging
import os
import sys
import math
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(__file__))
from stage1_map import MapGraphManager

from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def haversine(coord1, coord2):
    R = 6371000 # m
    lat1, lon1 = math.radians(coord1[0]), math.radians(coord1[1])
    lat2, lon2 = math.radians(coord2[0]), math.radians(coord2[1])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

class DRTOfflineRouter:
    """
    Pełnoprawny silnik DRT z Oknami Czasowymi (VRPTW-PD) + Grupowanie Pasażerów (Clustering).
    Wspólne wirtualne przystanki dla pasażerów w promieniu do 500m.
    """
    def __init__(self, map_manager: MapGraphManager, starts: list, ends: list, requests: list, fleet: list = None, start_time: str = "06:00"):
        self.manager = map_manager
        self.starts_coords = starts
        self.ends_coords = ends
        self.raw_requests = requests 
        self.start_datetime = datetime.strptime(start_time, "%H:%M")
        
        if fleet is None:
            self.fleet = [
                {"id": "Autokar (Kłodzko)", "capacity": 40},
                {"id": "Sprinter (Polanica)", "capacity": 15},
                {"id": "Mały Bus (Bystrzyca)", "capacity": 9}
            ]
        else:
            self.fleet = fleet
            
        self.num_vehicles = len(self.fleet)
        self.vehicle_capacities = [v["capacity"] for v in self.fleet]
        
        # 1. CLUSTERING PASAŻERÓW W WIRTUALNE PRZYSTANKI (Max 500m odstępu)
        self.requests = self._cluster_requests(self.raw_requests, radius_m=500, time_window_min=30)
        
        self.pickups_coords = [r["pickup"] for r in self.requests]
        self.dropoffs_coords = [r["dropoff"] for r in self.requests]
        
        self.locations = self.starts_coords + self.ends_coords + self.pickups_coords + self.dropoffs_coords
        
        self.starts_indices = list(range(self.num_vehicles))
        self.ends_indices = list(range(self.num_vehicles, 2 * self.num_vehicles))
        
        self.pickup_start_idx = 2 * self.num_vehicles
        self.dropoff_start_idx = 2 * self.num_vehicles + len(self.requests)
        
        self.time_matrix = []

    def _cluster_requests(self, raw_requests, radius_m=500, time_window_min=30):
        logger.info(f"Grupowanie {len(raw_requests)} zgłoszeń na wirtualne przystanki (promień {radius_m}m)...")
        clusters = []
        for req in raw_requests:
            added = False
            req_time_dt = datetime.strptime(req["req_time"], "%H:%M")
            
            for cl in clusters:
                if cl["dropoff"] == req["dropoff"] and cl["type"] == req["type"]:
                    cl_time_dt = datetime.strptime(cl["req_time"], "%H:%M")
                    # Różnica czasu max 30 min
                    if abs((req_time_dt - cl_time_dt).total_seconds()) <= time_window_min * 60:
                        # Różnica dystansu max 500m od środka klastra
                        if haversine(cl["pickup"], req["pickup"]) <= radius_m:
                            cl["original_requests"].append(req)
                            cl["pax"] += req["pax"]
                            
                            # Uaktualnij centroid (Wirtualny Przystanek to środek ciężkości osiedla)
                            n = len(cl["original_requests"])
                            new_lat = (cl["pickup"][0] * (n-1) + req["pickup"][0]) / n
                            new_lon = (cl["pickup"][1] * (n-1) + req["pickup"][1]) / n
                            cl["pickup"] = (new_lat, new_lon)
                            added = True
                            break
                            
            if not added:
                clusters.append({
                    "pickup": req["pickup"],
                    "dropoff": req["dropoff"],
                    "pax": req["pax"],
                    "req_time": req["req_time"],
                    "type": req["type"],
                    "original_requests": [req]
                })
                
        # Dociągamy centroidy Wirtualnych Przystanków do fizycznej drogi
        for cl in clusters:
            nearest_node = self.manager.get_nearest_node(cl["pickup"])
            cl["pickup"] = (self.manager.graph.nodes[nearest_node]['y'], self.manager.graph.nodes[nearest_node]['x'])
            
        logger.info(f"Skompresowano do {len(clusters)} wirtualnych przystanków!")
        return clusters

    def build_time_matrix(self):
        logger.info(f"Budowanie macierzy czasu dla {len(self.locations)} punktów...")
        matrix = []
        for i, origin in enumerate(self.locations):
            row = []
            for j, dest in enumerate(self.locations):
                if i == j:
                    row.append(0)
                else:
                    path = self.manager.calculate_shortest_path(origin, dest)
                    if path:
                        travel_time = int(self.manager.get_path_travel_time(path)) + 30
                        row.append(travel_time)
                    else:
                        row.append(999999)
            matrix.append(row)
        
        self.time_matrix = matrix
        return matrix

    def solve(self):
        if not self.time_matrix:
            self.build_time_matrix()
            
        manager = pywrapcp.RoutingIndexManager(
            len(self.locations), 
            self.num_vehicles, 
            self.starts_indices, 
            self.ends_indices
        )
        routing = pywrapcp.RoutingModel(manager)

        def time_callback(from_index, to_index):
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            return self.time_matrix[from_node][to_node]

        transit_callback_index = routing.RegisterTransitCallback(time_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

        routing.AddDimension(
            transit_callback_index,
            3600, 
            43200, 
            False, 
            'Time'
        )
        time_dimension = routing.GetDimensionOrDie('Time')

        def demand_callback(from_index):
            from_node = manager.IndexToNode(from_index)
            if from_node < self.pickup_start_idx: return 0 
            if from_node < self.dropoff_start_idx: return self.requests[from_node - self.pickup_start_idx]["pax"] 
            return -self.requests[from_node - self.dropoff_start_idx]["pax"]
            
        demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
        routing.AddDimensionWithVehicleCapacity(
            demand_callback_index,
            0,
            self.vehicle_capacities,
            True,
            'Capacity'
        )

        for i, req in enumerate(self.requests):
            pickup_node = self.pickup_start_idx + i
            dropoff_node = self.dropoff_start_idx + i
            
            pickup_index = manager.NodeToIndex(pickup_node)
            dropoff_index = manager.NodeToIndex(dropoff_node)
            
            routing.AddPickupAndDelivery(pickup_index, dropoff_index)
            routing.solver().Add(routing.VehicleVar(pickup_index) == routing.VehicleVar(dropoff_index))
            # Relaxed max ride time to 90 minutes (5400s) to guarantee a solution
            routing.solver().Add(time_dimension.CumulVar(dropoff_index) <= time_dimension.CumulVar(pickup_index) + 5400)
            
            req_time_dt = datetime.strptime(req["req_time"], "%H:%M")
            time_diff_sec = int((req_time_dt - self.start_datetime).total_seconds())
            if time_diff_sec < 0: time_diff_sec = 0 
                
            if req["type"] == "arrival":
                # Szerokie okno 60 minut przed czasem, do 15 min po czasie
                min_arr = max(0, time_diff_sec - 3600)
                max_arr = time_diff_sec + 900
                time_dimension.CumulVar(dropoff_index).SetRange(min_arr, max_arr)
            else:
                min_dep = max(0, time_diff_sec - 900)
                max_dep = time_diff_sec + 3600
                time_dimension.CumulVar(pickup_index).SetRange(min_dep, max_dep)

        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        search_parameters.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        search_parameters.time_limit.seconds = 15 
        
        logger.info("Szukanie rozwiązania z grupowaniem i oknami czasowymi...")
        solution = routing.SolveWithParameters(search_parameters)

        if solution:
            return self._extract_routes(manager, routing, solution)
        else:
            logger.error("Brak rozwiązania!")
            return None

    def _extract_routes(self, manager, routing, solution):
        routes = {}
        for vehicle_id in range(self.num_vehicles):
            index = routing.Start(vehicle_id)
            route_nodes = []
            while not routing.IsEnd(index):
                route_nodes.append(manager.IndexToNode(index))
                index = solution.Value(routing.NextVar(index))
            route_nodes.append(manager.IndexToNode(index))
            
            bus_name = self.fleet[vehicle_id]["id"]
            routes[bus_name] = {
                "path_indexes": route_nodes,
                "time_seconds": 0, # Placeholder
                "capacity_max": self.fleet[vehicle_id]["capacity"],
                "stops": len(route_nodes) - 2
            }
        return routes

    def save_routes_map(self, routes: dict, filepath: str = 'trasy_busow.html'):
        import folium
        from folium import plugins
        logger.info("Generowanie mapy z Wirtualnymi Przystankami...")
        
        m = folium.Map(location=[self.starts_coords[0][0], self.starts_coords[0][1]], zoom_start=11, tiles="OpenStreetMap")
        
        # Rysowanie wszystkich indywidualnych domów (ludziki w domach) i ich drogi do przystanku
        for req in self.requests:
            virt_stop = req["pickup"]
            
            # Punkt zbiorczy (Wirtualny Przystanek na drodze)
            folium.Marker(
                virt_stop, 
                tooltip=f"🚏 WIRTUALNY PRZYSTANEK\nOdbiera {req['pax']} osób", 
                icon=folium.Icon(color='orange', icon='users', prefix='fa')
            ).add_to(m)
            
            # Ludzie idący z domów do tego przystanku
            for orig_req in req["original_requests"]:
                house_loc = orig_req["pickup"]
                name = orig_req["name"]
                # Mała ikonka domku (House)
                folium.CircleMarker(house_loc, radius=4, color='gray', fill=True, tooltip=name).add_to(m)
                # Przerywana linia z domu do wspólnego przystanku (Dojście pieszko)
                folium.PolyLine([house_loc, virt_stop], color='red', weight=2, dash_array='4, 4', tooltip=f"Dojście pieszko ({name})").add_to(m)
                
            # Punkt wysiadki
            folium.CircleMarker(req["dropoff"], radius=8, color='red', fill=True, tooltip=f"🏁 CEL: {req['pax']} osób").add_to(m)

        for i, start_loc in enumerate(self.starts_coords):
            folium.Marker(start_loc, tooltip=f"🟢 BAZA: {self.fleet[i]['id']}", icon=folium.Icon(color='darkgreen', icon='home', prefix='fa')).add_to(m)

        colors = ['blue', 'purple', 'darkred']
        
        for i, (bus_name, info) in enumerate(routes.items()):
            path_idx = info["path_indexes"]
            if len(path_idx) <= 2:
                continue 
                
            color = colors[i % len(colors)]
            full_route_coords = []
            
            for j in range(len(path_idx) - 1):
                orig_point = self.locations[path_idx[j]]
                dest_point = self.locations[path_idx[j+1]]
                
                shortest_path_nodes = self.manager.calculate_shortest_path(orig_point, dest_point)
                if shortest_path_nodes:
                    for node in shortest_path_nodes:
                        lat = self.manager.graph.nodes[node]['y']
                        lon = self.manager.graph.nodes[node]['x']
                        full_route_coords.append((lat, lon))
            
            polyline = folium.PolyLine(full_route_coords, color=color, weight=6, opacity=0.8, tooltip=f"Trasa: {bus_name}")
            polyline.add_to(m)
            
            plugins.PolyLineTextPath(polyline, '\u27A4', repeat=True, offset=7, attributes={'fill': color, 'font-weight': 'bold', 'font-size': '20'}).add_to(m)
            
        m.save(filepath)
        logger.info(f"Mapa zapisana jako {filepath}")
