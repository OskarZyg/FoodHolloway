# Read POIs such as amenities and shops
# =====================================
import json

from matplotlib.figure import Figure
from pyrosm import OSM
fp = "data.osm.pbf"
# Initialize the OSM parser object
osm = OSM(fp)

# By default pyrosm reads all elements having "amenity", "shop" or "tourism" tag
# Here, let's read only "amenity" and "shop" by applying a custom filter that
# overrides the default filtering mechanism
custom_filter = {"fhrs:id": True}
pois = osm.get_pois(custom_filter=custom_filter)

# Gather info about POI type (combines the tag info from "amenity" and "shop")

pois['fsa_id'] = pois['tags'].apply(lambda x: json.loads(x).get('fhrs:id') if x else None)
print(pois)

# Plot
ax = pois.plot(column='poi_type', markersize=3, figsize=(12,12), legend=True, legend_kwds=dict(loc='upper left', ncol=5, bbox_to_anchor=(1, 1)))

# Get the figure from the axes and save it
fig = ax.get_figure()
fig.savefig('test.pdf', bbox_inches='tight')  # bbox_inches='tight' ensures legend isn't cut off
