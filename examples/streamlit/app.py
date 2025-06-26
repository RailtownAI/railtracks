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

# Title
st.title("RC Framework Demo")

# Create two columns
left_col, right_col = st.columns([1, 2])

with left_col:
    st.subheader("💬 AI Chat Interface")
    
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
    st.subheader("🎛️ Run Visualizer")
    
    # Create an instance of our component with a constant `name` arg, and
    # print its output value.
    num_clicks = my_component("World")
    st.markdown("You've clicked %s times!" % int(num_clicks))
    
    # Add some additional info about the component
    st.info("This is your custom React component running in the right column!")

# Add some test code to play with the component while it's in development.
# During development, we can run this just as we would any other Streamlit
# app: `$ streamlit run my_component/example.py`

 