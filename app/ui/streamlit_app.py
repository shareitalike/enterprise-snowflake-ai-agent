import streamlit as st
import requests
import uuid

# Constants
API_URL = "http://localhost:8000/query"

st.set_page_config(
    page_title="Enterprise Snowflake Intelligence Agent",
    page_icon="❄️",
    layout="wide"
)

st.title("❄️ Enterprise Snowflake Intelligence Agent")
st.markdown("A retrieval-first, evidence-driven AI agent for enterprise data assets.")

# Initialize chat history and session ID
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# React to user input
if prompt := st.chat_input("Ask about tables, columns, lineage, or governance..."):
    # Display user message in chat message container
    st.chat_message("user").markdown(prompt)
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Display assistant response in chat message container
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        
        try:
            # Call the FastAPI backend
            with st.spinner("Thinking (LLM Function Calling in progress)..."):
                payload = {
                    "query": prompt,
                    "session_id": st.session_state.session_id
                }
                response = requests.post(API_URL, json=payload)
                response.raise_for_status()
                data = response.json()
                
                full_response = data["response"]
                
                # Show debug info in an expander
                with st.expander("Agent Debug Trace (Function Calling)"):
                    st.write(f"**Tools Called**: {', '.join(data['intents'])}")
                    st.write(f"**Execution Plan**: {data['plan']}")

                message_placeholder.markdown(full_response)
                
                # Add assistant response to chat history
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                
        except requests.exceptions.ConnectionError:
            st.error("Could not connect to the API. Is the FastAPI server running?")
        except Exception as e:
            st.error(f"An error occurred: {e}")
