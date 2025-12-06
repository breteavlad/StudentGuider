import folium
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import openrouteservice
import overpy
import webbrowser
import os
import re
import subprocess

class MapAssistant:
    def __init__(self, start_address="Cluj-Napoca, Romania"):
        self.start_address = start_address
        self.geolocator = Nominatim(user_agent="tts_map_agent")
        self.api = overpy.Overpass()
        self.client = openrouteservice.Client(key=os.getenv("ORS_API_KEY"))

    def search_place_osm(self, place_name, center_lat, center_lon, radius=5000):
        """Search for a place by name using Overpass API"""
        clean_name = place_name.lower().strip()
        queries = []
        
        # Query 1: Search by name tag
        queries.append(f"""
        [out:json];
        (
          node["name"~"{place_name}",i](around:{radius},{center_lat},{center_lon});
          way["name"~"{place_name}",i](around:{radius},{center_lat},{center_lon});
          relation["name"~"{place_name}",i](around:{radius},{center_lat},{center_lon});
        );
        out center;
        """)
        
        # Query 2: Search by amenity type
        amenity_keywords = {
            "library": "library",
            "cafeteria": "restaurant",
            "cafe": "cafe",
            "coffee": "cafe",
            "restaurant": "restaurant",
            "gym": "gym",
            "health": "clinic",
            "hospital": "hospital",
            "clinic": "clinic",
            "parking": "parking",
            "lab": "university",
            "building": "university"
        }
        
        for keyword, amenity_type in amenity_keywords.items():
            if keyword in clean_name:
                queries.append(f"""
                [out:json];
                (
                  node["amenity"="{amenity_type}"](around:{radius},{center_lat},{center_lon});
                  way["amenity"="{amenity_type}"](around:{radius},{center_lat},{center_lon});
                );
                out center;
                """)
                break
        
        # Query 3: Search by building tag
        if any(word in clean_name for word in ["building", "faculty", "complex", "center"]):
            queries.append(f"""
            [out:json];
            (
              node["building"]["name"~"{place_name}",i](around:{radius},{center_lat},{center_lon});
              way["building"]["name"~"{place_name}",i](around:{radius},{center_lat},{center_lon});
            );
            out center;
            """)
        
        # Try each query
        for query in queries:
            try:
                result = self.api.query(query)
                candidates = []
                
                for node in result.nodes:
                    name = node.tags.get("name", "Unnamed")
                    candidates.append((name, float(node.lat), float(node.lon)))
                
                for way in result.ways:
                    name = way.tags.get("name", "Unnamed")
                    candidates.append((name, float(way.center_lat), float(way.center_lon)))
                
                if candidates:
                    closest = min(candidates, key=lambda c: geodesic((center_lat, center_lon), (c[1], c[2])).km)
                    return closest
                    
            except Exception as e:
                print(f"[DEBUG] Query failed: {e}")
                continue
        
        return None

    def generate_map(self, place_name):
        start = self.geolocator.geocode(self.start_address)
        if not start:
            print("[ERROR] Start address not found.")
            return None

        # Detect "closest" type queries
        if "closest" in place_name.lower() or "nearest" in place_name.lower():
            keyword = place_name.lower().replace("closest", "").replace("nearest", "").strip()
            if not keyword:
                print("[WARN] No place type found in query.")
                return None

            result = self.search_place_osm(keyword, start.latitude, start.longitude)
            if not result:
                print(f"[WARN] No nearby {keyword} found.")
                return None
            
            dest_name, dest_lat, dest_lon = result
            dest_coords = (dest_lat, dest_lon)
        else:
            # Try OSM search first
            print(f"[DEBUG] Searching OSM for: {place_name}")
            osm_result = self.search_place_osm(place_name, start.latitude, start.longitude)
            
            if osm_result:
                dest_name, dest_lat, dest_lon = osm_result
                dest_coords = (dest_lat, dest_lon)
                print(f"[INFO] Found via OSM: {dest_name} at ({dest_lat}, {dest_lon})")
            else:
                # Fallback to direct geocoding
                print(f"[DEBUG] OSM search failed, trying geocoding for: {place_name}")
                dest = self.geolocator.geocode(place_name + ", Cluj-Napoca, Romania")
                if not dest:
                    print(f"[ERROR] Destination '{place_name}' not found.")
                    return None
                dest_name = place_name
                dest_coords = (dest.latitude, dest.longitude)
                print(f"[INFO] Found via geocoding: {dest_name} at {dest_coords}")

        # Get route from ORS
        try:
            coords = ((start.longitude, start.latitude), (dest_coords[1], dest_coords[0]))
            route = self.client.directions(coords)
            geometry = route['routes'][0]['geometry']
            decoded = openrouteservice.convert.decode_polyline(geometry)
            dist_km = route['routes'][0]['summary']['distance'] / 1000
        except Exception as e:
            print(f"[ERROR] Routing failed: {e}")
            dist_km = geodesic((start.latitude, start.longitude), dest_coords).km
            decoded = None

        # Create map
        m = folium.Map(location=[start.latitude, start.longitude], zoom_start=15)
        folium.Marker([start.latitude, start.longitude], popup="You", icon=folium.Icon(color="green")).add_to(m)
        folium.Marker(dest_coords, popup=dest_name, icon=folium.Icon(color="red")).add_to(m)
        
        if decoded:
            folium.PolyLine(decoded['coordinates'], color="blue", weight=5).add_to(m)

        map_file = os.path.abspath("route_map.html")
        m.save(map_file)
        
        #  Open browser in background without blocking
        try:
            # Use subprocess.Popen with DETACHED_PROCESS to not block
            subprocess.Popen(
                ['chromium-browser', '--new-window', map_file],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True  # Detach from parent process
            )
            print(f"[INFO] Map opened in browser (non-blocking)")
        except FileNotFoundError:
            # Fallback if chromium-browser not found
            try:
                subprocess.Popen(
                    ['chromium', '--new-window', map_file],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )
                print(f"[INFO] Map opened in browser (non-blocking)")
            except:
                print(f"[WARN] Could not open browser automatically")

        print(f"[INFO] Map saved to {map_file} - {dest_name} ({dist_km:.2f} km away).")
        
        # ✅ Return both values clearly
        return (float(dist_km), dest_name)