
import shapefile
import geopandas as gpd
from shapely.geometry import shape

def read_shapefile_pyshp(filepath):
    """Reads a shapefile using pyshp (no GDAL dependency) and returns a GeoDataFrame."""
    sf = shapefile.Reader(filepath)
    fields = [x[0] for x in sf.fields][1:]
    records = sf.records()
    shps = sf.shapes()
    
    geoms = [shape(s) for s in shps]
    data = []
    for r in records:
        data.append(dict(zip(fields, r)))
    
    gdf = gpd.GeoDataFrame(data, geometry=geoms)
    return gdf
