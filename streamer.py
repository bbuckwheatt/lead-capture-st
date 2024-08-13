import streamlit as st
import json
from openai import OpenAI

# Initialize OpenAI client
openai_api_key = st.secrets["OPENAI_API_KEY"]
client = OpenAI(api_key=openai_api_key)

st.set_page_config(layout="wide")

# Ensure session states are initialized
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'lead_info' not in st.session_state:
    st.session_state.lead_info = {'name': '', 'email': ''}
if 'message_count' not in st.session_state:
    st.session_state.message_count = 0
if 'lead_captured' not in st.session_state:
    st.session_state.lead_captured = False
if 'welcome_displayed' not in st.session_state:
    st.session_state.welcome_displayed = False
if 'previous_capture_mode' not in st.session_state:
    st.session_state.previous_capture_mode = None

def reset_app():
    st.session_state.messages = []
    st.session_state.lead_info = {'name': '', 'email': ''}
    st.session_state.message_count = 0
    st.session_state.lead_captured = False
    st.session_state.welcome_displayed = False
    st.rerun()

def load_prompt(file_path):
    try:
        with open(file_path, 'r') as file:
            return file.read()
    except FileNotFoundError:
        print(f"The file {file_path} was not found.")
        return ""

class Agent:
    def __init__(self, api_key, system_prompt):
        self.client = OpenAI(api_key=api_key)
        self.system_prompt = system_prompt

    def chat(self, query, messages):
        conversation_history = [{"role": "system", "content": self.system_prompt}] + messages + [{"role": "user", "content": query}]
        response = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=conversation_history,
            max_tokens=4096
        )
        return response.choices[0].message.content

class Listener(Agent):
    def listen(self, query):
        response = super().chat(query, [])
        try:
            response_json = json.loads(response)
            return response_json
        except json.JSONDecodeError:
            return {"name": "", "email": ""}

# Initialize agents
general_agent = Agent(openai_api_key, "You are a helpful assistant that can answer questions and provide information.")
listener_agent = Listener(openai_api_key, load_prompt("listener.txt"))

# Sidebar
with st.sidebar:
    st.title('Lead Capture Settings')
    st.button('Reset Chat', on_click=reset_app)
    lead_capture_enabled = st.checkbox("Enable Lead Capture", value=True)
    capture_mode = st.radio("Capture Mode", ["Hard", "Soft"])
    if capture_mode == "Hard":
        messages_before_capture = st.number_input("Messages before lead capture", min_value=1, value=3)

# Check if capture mode has changed and reset if it has
if 'capture_mode' not in st.session_state or st.session_state.capture_mode != capture_mode:
    st.session_state.capture_mode = capture_mode
    reset_app()

# Main chat interface
st.title("Lead Capture Chat")

# Set up system message for soft capture mode
soft_capture_prompt = """
You are a helpful assistant. At the end of EVERY response, politely ask for any missing information:
- If the user's name is unknown, ask for their name.
- If the user's email is unknown, ask for their email.
- If both are unknown, ask for both.
Do this EVERY time, without fail, until both name and email are provided.
"""

# Display chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# Display welcome message if it's a new session
if not st.session_state.welcome_displayed:
    welcome_message = "How may I assist you today?"
    if lead_capture_enabled and capture_mode == "Soft":
        welcome_message += " Before we begin, could you please provide your name and email address?"
    st.chat_message("assistant").write(welcome_message)
    st.session_state.messages.append({"role": "assistant", "content": welcome_message})
    st.session_state.welcome_displayed = True

# User input
user_input = st.chat_input("Type your message here...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.chat_message("user").write(user_input)
    st.session_state.message_count += 1

    # Always listen for lead information
    listener_response = listener_agent.listen(user_input)
    
    # Update lead info if new information is provided
    if isinstance(listener_response, dict):
        if listener_response.get('name'):
            st.session_state.lead_info['name'] = listener_response['name']
        if listener_response.get('email'):
            st.session_state.lead_info['email'] = listener_response['email']
    
    # Check if both name and email are now populated
    if st.session_state.lead_info['name'] and st.session_state.lead_info['email'] and not st.session_state.lead_captured:
        st.session_state.lead_captured = True
        success_message = f"Lead captured: {st.session_state.lead_info['name']} ({st.session_state.lead_info['email']})"
        st.success(success_message)

    # Process user input
    if lead_capture_enabled and capture_mode == "Hard" and not st.session_state.lead_captured and st.session_state.message_count >= messages_before_capture:
        # Use lead capture agent
        lead_capture_agent = Agent(openai_api_key, load_prompt("leadcapture.txt"))
        response = lead_capture_agent.chat(user_input, st.session_state.messages)
    else:
        # Use general agent with soft capture if enabled
        if lead_capture_enabled and capture_mode == "Soft" and not st.session_state.lead_captured:
            current_system_prompt = f"{general_agent.system_prompt}\n{soft_capture_prompt}"
            temp_agent = Agent(openai_api_key, current_system_prompt)
            response = temp_agent.chat(user_input, st.session_state.messages)
        else:
            response = general_agent.chat(user_input, st.session_state.messages)

    st.session_state.messages.append({"role": "assistant", "content": response})
    st.chat_message("assistant").write(response)

# Display current lead info
if st.session_state.lead_info['name'] or st.session_state.lead_info['email']:
    lead_info_message = "Partial lead info captured:"
    if st.session_state.lead_info['name']:
        lead_info_message += f"\nName: {st.session_state.lead_info['name']}"
    if st.session_state.lead_info['email']:
        lead_info_message += f"\nEmail: {st.session_state.lead_info['email']}"
    st.sidebar.info(lead_info_message)

if st.session_state.lead_captured:
    st.sidebar.success(f"Lead fully captured: {st.session_state.lead_info['name']} ({st.session_state.lead_info['email']})")