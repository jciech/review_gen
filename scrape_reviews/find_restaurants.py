import httpx
from math import radians, cos, sin, asin, sqrt
import csv

async def fetch(url: str):
    async with httpx.AsyncClient() as client:
        r = await client.get(url)
        return r.text

def haversine(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    r = 6371
    return c * r

def parse_dms(dms_str):
    dms_str = dms_str.strip()
    direction = dms_str[-1]
    
    dms_str = dms_str[:-1].replace('"', '').replace("'", '')
    
    parts = dms_str.split('°')
    degrees = float(parts[0])
    
    minutes_seconds = parts[1] if len(parts) > 1 else "0"
    minutes_parts = minutes_seconds.split('.')
    
    if len(minutes_parts) == 1:
        minutes = float(minutes_parts[0])
        seconds = 0
    else: 
        minutes = float(minutes_parts[0])
        seconds = float("0." + minutes_parts[1]) * 60
    
    decimal = degrees + minutes/60 + seconds/3600
    
    if direction in ['S', 'W']:
        decimal = -decimal
        
    return decimal

async def main():
    lat = 51
    lon = 0  
    
    print(f"Searching for restaurants within 3km of coordinates: {lat}, {lon}")
    
    search_radius = 4000 
    overpass_query = f"""
    [out:json];
    node["amenity"="restaurant"](around:{search_radius},{lat},{lon});
    out body;
    """
    
    overpass_url = "https://overpass-api.de/api/interpreter"
    
    async with httpx.AsyncClient() as client:
        response = await client.post(overpass_url, data={"data": overpass_query})
        data = response.json()
    
    restaurants = []
    
    for node in data.get("elements", []):
        node_lat = node.get("lat")
        node_lon = node.get("lon")
        distance = haversine(lon, lat, node_lon, node_lat)
        
        if distance <= 3:
            name = node.get("tags", {}).get("name", "Unnamed restaurant")
            cuisine = node.get("tags", {}).get("cuisine", "")
            address = node.get("tags", {}).get("addr:street", "") + " " + node.get("tags", {}).get("addr:housenumber", "")
            address = address.strip()
            
            restaurants.append({
                "name": name,
                "distance": distance,
                "lat": node_lat,
                "lon": node_lon,
                "cuisine": cuisine,
                "address": address
            })
    
    restaurants.sort(key=lambda x: x["distance"])
    
    csv_filename = f"restaurants_near_{lat}_{lon}.csv"
    with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ["name", "distance", "lat", "lon", "cuisine", "address"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        for restaurant in restaurants:
            writer.writerow(restaurant)
    
    print(f"Saved {len(restaurants)} restaurants to {csv_filename}")
    
    if restaurants:
        print(f"Found {len(restaurants)} restaurants within 3km:")
        for i, restaurant in enumerate(restaurants, 1):
            print(f"{i}. {restaurant['name']} - {restaurant['distance']:.2f}km")
    else:
        print("No restaurants found within 3km.")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main()) 