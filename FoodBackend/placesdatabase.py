import dataclasses
import json
import sqlite3

import geopandas
from pyrosm import OSM
from shapely import Point

PLACE_MIGRATION = """
CREATE TABLE IF NOT EXISTS pois (
    fsa_id TEXT PRIMARY KEY,
    name TEXT,
    amenity TEXT
);
"""

@dataclasses.dataclass
class FoodPlace:
    fsa_id: str
    name: str
    amenity: str
    lat: float
    lon: float

class PlacesDatabase:
    def __init__(self):
        self.db = sqlite3.connect('places.db', check_same_thread=False)
        self.cursor = self.db.cursor()
        self.cursor.executescript(PLACE_MIGRATION)

    def insert_place(self, fhrs_id: int, place_name: str, place_type: str):
        self.cursor.execute(
            "INSERT INTO FoodPlace (FhrsId, PlaceName, PlaceType) VALUES (?,?,?) ON CONFLICT(FhrsId) DO UPDATE SET PlaceName = excluded.PlaceName, PlaceType = excluded.PlaceType",
            (fhrs_id, place_name, place_type, place_name)
        )
        self.db.commit()

class PlacesManager:
    def __init__(self, fp: str, cursor: sqlite3.Cursor):
        self.osm = OSM(fp)
        self.pois: geopandas.GeoDataFrame = self.osm.get_pois(custom_filter={"fhrs:id": True})
        self.pois['fsa_id'] = self.pois['tags'].apply(lambda x: json.loads(x).get('fhrs:id') if x else None)
        self.pois['amenity'] = self.pois['tags'].apply(lambda x: json.loads(x).get('amenity') if x else None)

        # Filter for non-null name and amenity
        self.pois = self.pois[
            self.pois['name'].notna() &
            self.pois['amenity'].notna()
        ]

        # Filter for specific amenity types
        allowed_amenities = ['restaurant', 'pub', 'fast_food', 'cafe', 'bar', 'ice_cream', 'cinema', 'events_venue', 'theatre']
        self.pois = self.pois[self.pois['amenity'].isin(allowed_amenities)]

        # Then deduplicate and set index
        self.pois = self.pois.drop_duplicates(subset='fsa_id').set_index('fsa_id')

        self.pois = self.pois.to_crs(epsg=3857)  # Project to meters ONCE
        _ = self.pois.sindex  # Build spatial index ONCE (happens automatically on first access)

        # Get centroids and convert back to lat/lon
        centroids_wgs84 = self.pois.geometry.centroid.to_crs(epsg=4326)
        self.pois['lat'] = centroids_wgs84.y
        self.pois['lon'] = centroids_wgs84.x

        for fsa_id, row in self.pois.iterrows():  # iterrows returns (index, row)
            cursor.execute(
                "INSERT OR IGNORE INTO pois (fsa_id, name, amenity) VALUES (?, ?, ?)",
                (fsa_id, row['name'], row['amenity'])
            )
        cursor.connection.commit()

    def find_nearby_pois(self, lon: float, lat: float, radius_m=500) -> geopandas.GeoDataFrame:
        # Create search point in WGS84 (input is always lon/lat)
        center = Point(lon, lat)

        # ALWAYS convert to match POIs CRS (which is EPSG:3857)
        center = geopandas.GeoSeries([center], crs='EPSG:4326').to_crs(self.pois.crs).iloc[0]

        # Use spatial index for fast bounding box search
        bbox = center.buffer(radius_m).bounds
        possible_matches_idx = list(self.pois.sindex.intersection(bbox))

        # Refine with exact distance check
        candidates = self.pois.iloc[possible_matches_idx]
        nearby = candidates[candidates.distance(center) <= radius_m]

        return nearby
