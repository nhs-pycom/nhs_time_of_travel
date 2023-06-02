from geopy.geocoders import Nominatim

geolocator = Nominatim(user_agent="my_app")
import pandas as pd
import osmnx as ox
import networkx as nx
from shapely.geometry.polygon import Point, Polygon
import folium
import geopandas as gpd
from haversine import haversine, Unit


class GeocodingError(Exception):
    pass


def main(address, radius_miles, speed):
    if address.strip() == "":
        raise GeocodingError("No address entered, please enter an address")

    location = Nominatim(user_agent="my_app").geocode(address, addressdetails=True)
    radius_metres = radius_miles * 1609
    if location is None:
        raise GeocodingError(
            "Address could not be found, please check the example format {}".format(
                address
            )
        )

    origin = (location.latitude, location.longitude)

    G = ox.graph_from_point(origin, dist=radius_metres, network_type="drive")

    lsoa_pop = pd.read_csv("../data/lsoa_global_number_residents_2021.csv")
    gdf = gpd.read_file("../data/LSOA_2021_EW_BGC.shp")

    gdf_filtered = filter_grid_lsoas_to_origin(gdf, radius_miles, origin)
    lsoa_codes = gdf_filtered["LSOA21CD"].tolist()
    lsoa_data = {lsoa_code: {} for lsoa_code in lsoa_codes}

    for index, row in gdf_filtered.iterrows():
        lsoa_code = row["LSOA21CD"]
        if lsoa_code in lsoa_data:
            lsoa_data[lsoa_code]["Latitude"] = row["geometry"].centroid.y
            lsoa_data[lsoa_code]["Longitude"] = row["geometry"].centroid.x
            node = ox.distance.nearest_nodes(
                G, row["geometry"].centroid.x, row["geometry"].centroid.y
            )
            lsoa_data[lsoa_code]["Node"] = node

    lsoa_population = {}
    for lsoa_code in lsoa_data:
        population = lsoa_pop.loc[lsoa_pop["LSOA21CD"] == lsoa_code, "Population"].iloc[
            0
        ]
        try:
            latitude = lsoa_data[lsoa_code]["Latitude"]
        except KeyError:
            print(f"KeyError: Latitude not found for LSOA code {lsoa_code}")
            latitude = None
        try:
            longitude = lsoa_data[lsoa_code]["Longitude"]
        except KeyError:
            print(f"KeyError: Longitude not found for LSOA code {lsoa_code}")
            longitude = None
        lsoa_population[lsoa_code] = {
            "Population": population,
            "Latitude": latitude,
            "Longitude": longitude,
        }

    # get LSOAs within search radius
    lsoas_in_radius = []
    for lsoa_code, data in lsoa_data.items():
        distance = haversine(origin, (data["Latitude"], data["Longitude"]), unit="km")
        if distance <= radius_metres / 1000:
            lsoas_in_radius.append(lsoa_code)

    m = folium.Map(location=origin, zoom_start=12)
    folium.Marker(location=origin, tooltip=address).add_to(m)
    folium.Circle(
        location=origin,
        radius=radius_metres,
        color="red",
        fill=False,
        tooltip="Search Radius",
    ).add_to(m)

    add_lsoas_to_map(lsoas_in_radius, m, gdf_filtered, lsoa_population)

    avg_travel_time, population_covered = get_average_travel_times(
        origin, lsoa_population, G, lsoas_in_radius, speed
    )

    return m, avg_travel_time, population_covered


def filter_grid_lsoas_to_origin(gdf, radius_miles, origin):
    """Filter a Geo DataFrame to just the rows which overlap a circle at origin origin, with radius radius_miles"""
    # Convert the origin to National grid (so in m)
    d = {'col1': ['name1'], 'geometry': [Point(origin[1], origin[0])]}
    origin_gdf = gpd.GeoDataFrame(d, crs=4326)
    origin_gdf = origin_gdf.to_crs(27700)
    origin_grid = origin_gdf.at[0, 'geometry']
    # find the LSOAs in national grid space
    filtered_gdf = gdf[gdf.distance(origin_grid) < radius_miles * 1609]
    # convert to lat long for display
    return filtered_gdf.to_crs(4326)


def get_average_travel_times(origin, lsoa_population, G, lsoas_in_radius, speed_mph):
    # calculate shortest paths from origin to LSOAs within search radius
    travel_times_secs = []
    weighted_traveltimes = []
    weights = []
    for lsoa_code in lsoas_in_radius:
        destination = (lsoa_population[lsoa_code]['Latitude'], lsoa_population[lsoa_code]['Longitude'])
        try:
            length_miles = nx.shortest_path_length(G, source=ox.distance.nearest_nodes(G, origin[1], origin[0]),
                                                   target=ox.distance.nearest_nodes(G, destination[1], destination[0]),
                                                   weight='length') / 1609.34

            travel_time_sec = (length_miles / speed_mph) * 3600
            travel_times_secs.append(travel_time_sec)
            weight = lsoa_population[lsoa_code]['Population']
            weighted_traveltimes.append(travel_time_sec * weight)
            weights.append(weight)

        except nx.NetworkXNoPath:
            pass

    # calculate average travel time and population within search radius
    avg_weighted_travel_time = sum(weighted_traveltimes) / sum(weights) / 60
    population_covered = sum([lsoa_population[lsoa]['Population'] for lsoa in lsoas_in_radius])
    return round(avg_weighted_travel_time), round(population_covered)


def add_lsoas_to_map(lsoas, m, gdf_filtered, lsoa_population):
    #    for lsoa_code in lsoas:
    #        row = gdf_filtered.loc[gdf_filtered["LSOA21CD"] == lsoa_code].iloc[0]

    for i, row in gdf_filtered.iterrows():
        lsoa_code = row["LSOA21CD"]
        included = lsoa_code in lsoas
        population = lsoa_population[lsoa_code]["Population"]

        if row["geometry"].geom_type == "Polygon":
            lsoa_boundary = [
                tuple(reversed(coord))
                for coord in list(row["geometry"].exterior.coords)
            ]
        elif row["geometry"].geom_type == "MultiPolygon":
            largest_polygon = max(row["geometry"], key=lambda x: x.area)
            lsoa_boundary = [
                tuple(reversed(coord))
                for coord in list(largest_polygon.exterior.coords)
            ]

        lsoa_polygon = folium.Polygon(
            locations=lsoa_boundary,
            color="blue" if included else "red",
            fill=True,
            fill_color="blue" if included else "red",
            fill_opacity=0.2,
            tooltip=str(population),
        )

        lsoa_polygon.add_to(m)
