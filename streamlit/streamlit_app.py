import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import geojson
import base64
from scripts.py_walking_gp_practice_cambridge import dis_map
from functions.sidebar import sidebar as sidebar

st.set_page_config(
    page_title="NHS Time to travel",
)



st.title("🚂 MedicalMap - A Medical Geospatial Tool")

st.sidebar.success("Select a page above.")

st.markdown(
    """
    

    This work was led by Paul Carroll, Senior Data Scientist, Oliver Jones, Muhammed-Faaiz Shawanas, Mary Amanuel, as part of their roles with the Digital Analytics and Research Team at NHS England, and Nick Fortescue and Max Morozov, two brilliant engineers at GoogleHealth.

    The following page and accompanying GitHub repository contain the initial proof of concept and exploratory analysis for the design of a holistic and interactive mapping tool to support decision-making in health and social care.

    A mapping tool could support national and regional commissioning strategies by facilitating the placement of new services and the reconfiguration of existing ones. It could also contribute to saving costs for Trusts by providing a service for free, that is currently paid for. 

    Using open-source software and publicly accessible datasets we're able to show three pages so far here; First, Route Optimisation, aka the Travelling Salesman Problem. In a health context this could be used for planning district nurse visits, or ambulance patient drop-offs. The second, Multiple Shortest Routes, this could be used to help planning for staff routes to work, and could help with suggesting lower emissions ways to work; The third, Max Coverage Location, this is our concept piece for site scoring. e.g. a covid site or a new GP practice. A good comparison here would be how retailers look to score a new site, and how they approach the problem.

    Please reach out if you have page suggestions, or wish to contribute. Either raise an issue on the Github site, or email paul.carroll9@nhs.net, or github.com/pauliecarroll.  Thank you.

    Source page: https://nhsx.github.io/nhs_time_of_travel/
    
    
"""
)

sidebar(False)
