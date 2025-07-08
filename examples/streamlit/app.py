import streamlit as st
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from __init__ import my_component

# Page configuration
st.set_page_config(
    page_title="RC Framework Demo",
    page_icon="🤖",
    layout="wide"
) 

# Add custom CSS to remove top padding
st.markdown("""
<style>
    .block-container {
        padding-top: 0;
        padding-bottom: 0rem;
        padding-left: 5rem;
        padding-right: 5rem;
    }
    
    /* Remove top margin from the first element */
    .main .block-container > div:first-child {
        margin-top: 0;
    }
    
    /* Remove padding from the main container */
    .main {
        padding-top: 0;
    }
</style>
""", unsafe_allow_html=True)
 

 
st.subheader("🎛️ Agentic Flow Visualizer") 
num_clicks = my_component("World")
st.markdown("You've clicked %s times!" % int(num_clicks))
     
