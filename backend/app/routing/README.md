# Algorytm Trasowania DRT (Smart City)

Ten folder zawiera główny silnik algorytmiczny systemu transportu na żądanie (DRT - Demand Responsive Transport). Silnik odpowiada za wytyczanie optymalnych tras dla busów bez sztywnych rozkładów jazdy.

## Architektura i Etapy

Rozwiązanie podzielone jest na 4 fazy (Etapy):

### Etap 1: Graf Drogowy i Mapa (`stage1_map.py`)
- Wykorzystuje bibliotekę **OSMnx** do pobierania rzeczywistego układu dróg z serwerów OpenStreetMap (domyślnie obszar Kłodzka).
- Konwertuje ulice na graf skierowany (NetworkX).
- Wzbogaca każdą krawędź grafu (ulicę) o atrybuty czasu przejazdu na bazie lokalnych ograniczeń prędkości.
- Pozwala na wizualizację tras i węzłów na interaktywnej mapie z użyciem Folium (`save_map_html`).

### Etap 2: Optymalizacja Offline / Batch (`stage2_offline.py`)
- Wykorzystuje solver VRP z biblioteki **Google OR-Tools**.
- Buduje macierz dokładnego czasu przejazdu pomiędzy Hubem a wszystkimi pasażerami (Time Matrix).
- Dla zaplanowanych, stałych zleceń przypisuje pasażerów do dostępnych busów, minimalizując ogólny czas przejazdu oraz zapewniając jak najszybsze dotarcie floty na węzeł docelowy.

### Etap 3: Heurystyka Wstawiania Online (Dynamic Insertion)
*W trakcie implementacji...*
- Algorytm obsługujący wezwania ad-hoc.
- Dopisuje "wirtualne przystanki" do już ułożonych tras (z Etapu 2).
- Sprawdza warunek zachowania limitu czasu (np. nie opóźniając reszty o więcej niż 10 minut).

### Etap 4: Integracja i Dashboard
*W planach...*
- Podpięcie pod frontend oraz wizualizacja na żywo dla jury z odświeżającą się mapą (np. Folium z poziomu Streamlit lub Reacta).

---
## Uruchamianie Testów

Moduły są przygotowane do samodzielnego działania na przykładowych danych (Kłodzko + 6 mockowanych pasażerów). Będąc w katalogu `backend`, uruchom polecenia przez menedżera `uv`:

```bash
uv run app/routing/stage1_map.py
uv run app/routing/stage2_offline.py
```
