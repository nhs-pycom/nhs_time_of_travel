import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import cm
import networkx as nx
import osmnx as ox
import geopandas as gpd
import networkx as nx
from cartopy.geodesic import Geodesic
from shapely.geometry.polygon import Point, Polygon
from shapely.geometry import shape
from shapely.ops import unary_union
import nhstravel.loaders.lsoaloader as lsoaloader
import folium 
import streamlit as st

#generate network x map of a specified region of a specific travel type (walk, drive e.tc)
# without allow_output_mutation, st.cache is performing a hash of the entire graph on every run. This is taking a long time. Skip check
@st.cache(persist=True, allow_output_mutation=True)
def generate_networkx(region, type):
    G = ox.graph.graph_from_place(region, simplify = True, network_type = type)
    nodes, edges = ox.graph_to_gdfs(G)
    return G, nodes


#function to get osmid (node ids) for the potential target addresses given by the user
def get_target_nodes(G, list_of_target_addresses):
    list_of_target_nodes = []
    list_of_target_coords = []
    for target_address in list_of_target_addresses:
        target_coords = ox.geocode(target_address)
        target_node = ox.distance.nearest_nodes(G, X=target_coords[1], Y=target_coords[0])
        list_of_target_nodes.append(target_node)
        list_of_target_coords.append(target_coords)
    return list_of_target_nodes, list_of_target_coords


#function to call lsoa loaders library to import lsoa data for the given regin
def load_lsoa(region):
    print('building lsoa for ', region)
    lsoa_with_population_pd = lsoaloader.build_lsoa_data_frame_for_area_england(region)
    remapped_lsoa = lsoaloader.load_geo_json_shapefiles_for_lsoas(lsoa_with_population_pd, region)
    return remapped_lsoa

#genearte the collection of lsoas for each target location
def generate_neighboring_polys(remapped_lsoa, list_of_target_coords, radius):
    gd = Geodesic()

    list_of_neighboring_poly_dicts = []

    for target_coords in list_of_target_coords:
        target_point = Point(target_coords[1], target_coords[0])
        bounding_poly = Polygon(gd.circle(lon=target_coords[1], lat=target_coords[0], radius=radius))

        neighboring_polys = {'lsoa_codes':[], 'population':[], 'polygons':[]}
        for lsoa in remapped_lsoa['features']:
            lsoa_polygon = shape(lsoa['geometry'])
            if lsoa_polygon.contains(target_point) or bounding_poly.intersects(lsoa_polygon):
                neighboring_polys['lsoa_codes'].append(lsoa['properties']['LSOA21CD'])
                neighboring_polys['population'].append(lsoa['properties']['all ages'])
                neighboring_polys['polygons'].append(lsoa_polygon)

        list_of_neighboring_poly_dicts.append(neighboring_polys)

    return list_of_neighboring_poly_dicts

#funtion to generate the sample of nodes from each collection of lsoas for each target location
def generate_nodes_samples(list_of_neighboring_poly_dicts, list_of_target_nodes, nodes):
    list_of_nodes_samples = []
    for neighboring_polys, target_node in zip(list_of_neighboring_poly_dicts, list_of_target_nodes):
        nodes_sample = pd.DataFrame(columns = nodes.columns)
        list_of_lsoa_codes = []
        list_of_pops = []


        for i in range(len(neighboring_polys['polygons'])):
            lsoa = neighboring_polys['polygons'][i]
            for j in range(nodes.shape[0]):
                if lsoa.contains(nodes.iloc[j]['geometry']):
                    nodes_sample = nodes_sample.append(nodes.iloc[j])
                    list_of_lsoa_codes.append(neighboring_polys['lsoa_codes'][i])
                    list_of_pops.append(neighboring_polys['population'][i])

        nodes_sample['lsoa_codes'] = list_of_lsoa_codes
        nodes_sample['lsoa_population'] = list_of_pops

        nodes_sample = nodes_sample.drop(target_node)

        list_of_nodes_samples.append(nodes_sample)
    return list_of_nodes_samples


#creating a function to calculate a score from a list of lengths calculated from the target node to each of the 100 sample nodes
def create_score(list_of_lengths, list_of_multipliers):
    score = 1000
    for l, m in zip(list_of_lengths, list_of_multipliers):
        deduction = (((l/1000)/4.5)*60) * m * 5#get the length in km divide by speed 4.5 km/h then divide by 60 to get time in minutes
        score = score - deduction #decrement the score by the derivation of time taken to each of the 100 nodes
        return score

#define a function to calculate multiple shortest route lengths from the target node to each of the 100 sample nodes
def create_list_of_lengths(G, nodes_sample, target_node):
    list_of_lengths = []
    list_of_multipliers = []
    for node in nodes_sample.index:
        total_pop = nodes_sample['lsoa_population'].unique().sum()
        node_pop = nodes_sample['lsoa_population'][node]
        multiplier = 1 - (node_pop/total_pop)
        length = nx.shortest_path_length(G, source=node, target=target_node, weight='length') #calculate route from target node to sample node
        list_of_lengths.append(length) #append the length to the list
        list_of_multipliers.append(multiplier) #append the multipliers to the list for score creation
    
    return [list_of_lengths, list_of_multipliers]

#function to generate the score for each of the potential target sites provided using create_score()
def generate_target_scores(G, list_of_nodes_samples, list_of_target_nodes, list_of_target_addresses):
    target_scores = {}
    site_names = []
    for i in range(len(list_of_target_nodes)):
        nodes_sample = list_of_nodes_samples[i]
        site_name = 'Site {}'.format(i + 1)
        site_address = list_of_target_addresses[i]
        target_lengths = create_list_of_lengths(G, nodes_sample, list_of_target_nodes[i])
        target_scores[site_name] = create_score(target_lengths[0], target_lengths[1])
        print('The score for {}: {} is {}'.format(site_name, site_address, target_scores[site_name]))
        site_names.append(site_name)
    return site_names, target_scores

#fucntion to generate the multiple shortest routes from the target node to each of the sample nodes
def generate_msr(G, site_names, list_of_target_nodes, list_of_nodes_samples):
    target_to_node_routes = {}
    for site, target_node, nodes_sample in zip(site_names, list_of_target_nodes, list_of_nodes_samples):
        list_of_routes = []
        for node in nodes_sample.index:
            route = nx.shortest_path(G, source=node, target=target_node, weight='length') #calculate route from target node to sample node
            list_of_routes.append(route) #append the length to the list
        target_to_node_routes[site] = list_of_routes
    return target_to_node_routes


def generate_route_layers(G,
                       target_to_node_routes,
                       site_names,
                       list_of_target_addresses,
                       list_of_target_coords,
                       target_scores,
                       colors=['green', 'red', 'yellow', 'blue', 'pink', 'purple']):

    ''' Function to plot routes from target nodes to sample nodes for on a folium map
    
    Args: 
        G: Networkx graph of area 
        target_to_node_routes: Dict of site names to list of routes from that node to target
        site_names: list of sites
        list_of_target_addresses: list of target addresses (same length & order as site names)
        list_of_target_coords: list of target coords (same length & order as site names)
        target_scores: score for each target
        colors: (optional) colors for routes for each site

    Returns:
        Single folium map with all routes and markers with one layer per site
    '''
    result = []
    for i, (site, target_address, target_coords) in enumerate(zip(site_names, list_of_target_addresses, list_of_target_coords)):
        layer = routes_to_featuregroup(G, routes=target_to_node_routes[site], color=colors[i], name=site)
        iframe = folium.IFrame('<font face = "Arial"><b>{}:</b> {}. <br><br><b>{} Score:</b> {}</br></br></font>'.format(site, target_address, site, target_scores[site]))
        popup = folium.Popup(iframe, min_width=200, max_width=300)
        folium.Marker(location=target_coords,
                    popup = popup,
                    icon=folium.Icon(color=colors[i], 
                    icon='info-sign')).add_to(layer)
        result.append(layer)
    return result


def routes_to_featuregroup(G, routes, color, name):
    '''
    Convert a networkx route into a folium FeatureGroup
    
    Args:
        G: Networkx graph of area 
        routes: list of routes, each of which is a list of node indices
        color: color for lines in folium 
        name: name for resulting feature group

    Returns:
        a feature group with all routes as lines
    '''
    layer = folium.FeatureGroup(name=name)
    lines = [] 
    for route in routes:
        route_coords =[]
        for node in route:
            route_coords.append((G.nodes[node]['y'], G.nodes[node]['x']))
        lines.append(route_coords)
    folium.PolyLine(lines, color=color, weight=2, opacity=0.5).add_to(layer)
    
    return layer


def generate_lsoa_layer(remapped_lsoa, color='blue'):
    layer = folium.FeatureGroup(name='LSOAs')
    style = {'color': color}

    shape = folium.GeoJson(data=remapped_lsoa, style_function=lambda x:style)
    shape.add_to(layer)
    return layer


#save each of the folium maps as a folium object in the list route_maps to be displayed by streamlit
def save_maps(site_names, route_maps):
    for site_name, map in zip(site_names, route_maps):
        map.save('route map for {}.html'.format(site_name))


#main function to generate networkx map then generate the scores and folium map for each proposed target location
def mclp_main(region, list_of_target_addresses, radius):
    G, nodes = generate_networkx(region, 'walk')
    list_of_target_nodes, list_of_target_coords = get_target_nodes(G, list_of_target_addresses)
    remapped_lsoa = load_lsoa(region)
    list_of_neighboring_poly_dicts = generate_neighboring_polys(remapped_lsoa, list_of_target_coords, radius=radius)
    list_of_nodes_samples = generate_nodes_samples(list_of_neighboring_poly_dicts, list_of_target_nodes, nodes)
    site_names, target_scores = generate_target_scores(G, list_of_nodes_samples, list_of_target_nodes, list_of_target_addresses)
    target_to_node_routes = generate_msr(G, site_names, list_of_target_nodes, list_of_nodes_samples)

    first_target = list_of_target_coords[0]
    map = folium.Map(location=first_target,
                     tiles="cartodbpositron", 
                     zoom_start=13)

    generate_lsoa_layer(remapped_lsoa, color='blue').add_to(map)

    layers = generate_route_layers(G, target_to_node_routes, site_names, list_of_target_addresses, list_of_target_coords, target_scores)
    for layer in layers:
        layer.add_to(map)

    # TO DO: keep in front doesnt work to move lsoa's behind route layers on folium map

    # add a layer control to toggle the layers on and off
    folium.LayerControl().add_to(map)
    # save_maps(site_names, route_map)
    return target_scores, map


