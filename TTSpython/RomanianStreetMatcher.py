import folium
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import openrouteservice
import overpy
import webbrowser
import os
import re
import subprocess
from fuzzywuzzy import process, fuzz

class RomanianStreetMatcher:
    """Handles recognition of Romanian street names from English phonetic input"""
    
    def __init__(self, city="Cluj-Napoca"):
        self.city = city
        self.street_database = {}
        self.phonetic_variants = {}
        self._build_dictionaries()
    
    def _build_dictionaries(self):
        """Build Romanian street vocabulary and phonetic variants"""
        
        # Common Romanian street types with English phonetic variants
        self.street_types = {
            "strada": ["strada", "strata", "strада", "street"],
            "aleea": ["aleea", "aleia", "alea", "alley"],
            "bulevardul": ["bulevardul", "boulevard", "bulevard", "bulevar"],
            "calea": ["calea", "caleya", "kalea"],
            "piața": ["piața", "piata", "piatza", "square"],
            "șoseaua": ["șoseaua", "shoseaua", "soseaua"],
        }
        
        # Common Romanian street name words with phonetic variants
        self.common_words = {
            "plopilor": ["plopilor", "plopee lor", "plopiilor"],
            "eroilor": ["eroilor", "heroilor", "eroi lor", "eroy lor"],
            "republicii": ["republicii", "republic ii", "republici"],
            "libertății": ["libertății", "libertatii", "liberty"],
            "unirii": ["unirii", "uniri", "unity"],
            "mihai": ["mihai", "my high", "mihaj", "mihای"],
            "viteazu": ["viteazu", "vitazu", "viteazul"],
            "avram": ["avram", "abraham", "avam"],
            "iancu": ["iancu", "yanku", "ianku"],
            "horea": ["horea", "hoреа"],
            "cloșca": ["cloșca", "closca", "kloshka"],
            "crișan": ["crișan", "crisan", "krishan"],
            "memorandumului": ["memorandumului", "memorandum", "memorandumu"],
            "observatorului": ["observatorului", "observatory", "observator"],
            "donath": ["donath", "donat"],
            "gheorghe": ["gheorghe", "george", "gheorgh"],
            "doja": ["doja", "doya"],
            "emil": ["emil", "emeel"],
            "isac": ["isac", "isaac", "izak"],
            "napoca": ["napoca", "napoka"],
            "mănăștur": ["mănăștur", "manastur", "manashtur"],
            "zorilor": ["zorilor", "zori lor"],
            "grigorescu": ["grigorescu", "grigoresku"],
            "buna": ["buna", "boona"],
            "ziua": ["ziua", "ziwa"],
        }
    
    def fetch_streets_from_osm(self):
        """Fetch all street names from OpenStreetMap for the city"""
        api = overpy.Overpass()
        query = f"""
        [out:json];
        area["name"="{self.city}"]["admin_level"="8"]->.searchArea;
        (
          way["highway"]["name"](area.searchArea);
        );
        out tags;
        """
        
        try:
            result = api.query(query)
            streets = []
            for way in result.ways:
                if "name" in way.tags:
                    streets.append(way.tags["name"])
            
            # Remove duplicates and store
            self.street_database = {street.lower(): street for street in set(streets)}
            print(f"[INFO] Loaded {len(self.street_database)} streets from OSM")
            return list(self.street_database.values())
        except Exception as e:
            print(f"[WARN] Could not fetch streets from OSM: {e}")
            return []
    
    def normalize_romanian_text(self, text):
        """Convert Romanian text with phonetic variants to proper Romanian"""
        text = text.lower().strip()
        
        # Replace street type variants
        for proper, variants in self.street_types.items():
            for variant in variants:
                if variant in text:
                    text = text.replace(variant, proper)
                    break
        
        # Replace common word variants
        for proper, variants in self.common_words.items():
            for variant in variants:
                # Use word boundaries to avoid partial matches
                pattern = r'\b' + re.escape(variant) + r'\b'
                text = re.sub(pattern, proper, text, flags=re.IGNORECASE)
        
        return text
    
    def match_street(self, user_input):
        """
        Match user's phonetic input to actual Romanian street name
        Returns: (matched_street_name, confidence_score)
        """
        # Normalize the input first
        normalized = self.normalize_romanian_text(user_input)
        
        # If we have street database, use fuzzy matching
        if self.street_database:
            match, score = process.extractOne(
                normalized, 
                self.street_database.keys(),
                scorer=fuzz.token_sort_ratio
            )
            
            if score > 60:  # Confidence threshold
                proper_name = self.street_database[match]
                print(f"[DEBUG] Matched '{user_input}' -> '{proper_name}' (score: {score})")
                return proper_name, score
        
        # Fallback: return normalized version
        print(f"[DEBUG] No match found, using normalized: '{normalized}'")
        return normalized, 0
