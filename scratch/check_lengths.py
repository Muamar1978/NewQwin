
import os
import struct
from shapely.geometry import LineString

def get_road_length(shp_path):
    if not os.path.exists(shp_path):
        return "File not found"
    
    with open(shp_path, 'rb') as f:
        f.seek(100) # Header is 100 bytes
        total_length = 0
        while True:
            header = f.read(8)
            if not header: break
            record_num, content_len = struct.unpack('>II', header)
            shape_type = struct.unpack('<I', f.read(4))[0]
            
            if shape_type == 3: # PolyLine
                f.read(32) # Skip box
                num_parts, num_points = struct.unpack('<II', f.read(8))
                parts = struct.unpack('<' + 'I' * num_parts, f.read(4 * num_parts))
                points = []
                for _ in range(num_points):
                    points.append(struct.unpack('<dd', f.read(16)))
                
                # Simple single part for now
                if num_parts == 1:
                    line = LineString(points)
                    total_length += line.length
                else:
                    # Multi-part
                    for i in range(num_parts):
                        start = parts[i]
                        end = parts[i+1] if i+1 < num_parts else num_points
                        line = LineString(points[start:end])
                        total_length += line.length
            else:
                f.seek(content_len * 2 - 4, 1)
        return total_length

print(f"Road 1 Length: {get_road_length('road1.shp'):.2f} meters")
print(f"Road 2 Length: {get_road_length('road2.shp'):.2f} meters")
print(f"Road 3 Length: {get_road_length('road3.shp'):.2f} meters")
print(f"Road 4 Length: {get_road_length('road4.shp'):.2f} meters")
