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

# Create two columns
left_col, right_col = st.columns([1, 5])

with left_col:
    st.subheader("💬 Chat With Your Agents")
    
    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display chat messages from history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat input
    if prompt := st.chat_input("What would you like to know?"):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Display user message in chat message container
        with st.chat_message("user"):
            st.markdown(prompt)

        # Display assistant response in chat message container
        with st.chat_message("assistant"):
            response = f"Echo: {prompt}"  # Placeholder response - you can integrate with your AI here
            st.markdown(response)
        
        # Add assistant response to chat history
        st.session_state.messages.append({"role": "assistant", "content": response})

with right_col:
    st.subheader("🎛️ Agentic Flow Visualizer") 
    num_clicks = my_component("World")
    st.markdown("You've clicked %s times!" % int(num_clicks))
     

# Add some test code to play with the component while it's in development.
# During development, we can run this just as we would any other Streamlit
# app: `$ streamlit run my_component/example.py`

 