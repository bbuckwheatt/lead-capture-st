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
if 'current_agent' not in st.session_state:
    st.session_state.current_agent = 'general'
if 'lead_info' not in st.session_state:
    st.session_state.lead_info = {'name': '', 'email': ''}
if 'message_count' not in st.session_state:
    st.session_state.message_count = 0
if 'lead_captured' not in st.session_state:
    st.session_state.lead_captured = False

def reset_app():
    st.session_state.messages = []
    st.session_state.current_agent = 'general'
    st.session_state.lead_info = {'name': '', 'email': ''}
    st.session_state.message_count = 0
    st.session_state.lead_captured = False
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

    def chat(self, query):
        conversation_history = [{"role": "system", "content": self.system_prompt}] + \
                               st.session_state.messages + \
                               [{"role": "user", "content": query}]
        response = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=conversation_history,
            max_tokens=4096
        )
        return response.choices[0].message.content

class Listener(Agent):
    def listen(self, query):
        response = super().chat(query)
        try:
            response_json = json.loads(response)
            return response_json
        except json.JSONDecodeError:
            return {"verdict": False, "name": "", "email": ""}

# Initialize agents
general_agent = Agent(openai_api_key, "You are a helpful assistant that can answer questions and provide information.")
listener_agent = Listener(openai_api_key, load_prompt("listener.txt"))
lead_capture_agent = Agent(openai_api_key, load_prompt("leadcapture.txt"))

# Sidebar
with st.sidebar:
    st.title('Lead Capture Settings')
    st.button('Reset Chat', on_click=reset_app)
    lead_capture_enabled = st.checkbox("Enable Lead Capture", value=True)
    start_with_lead_capture = st.checkbox("Start with Lead Capture", value=False)
    messages_before_capture = st.number_input("Messages before lead capture", min_value=1, value=3)

# Set initial agent based on the toggle
if start_with_lead_capture and lead_capture_enabled and not st.session_state.lead_captured:
    st.session_state.current_agent = 'lead_capture'
else:
    st.session_state.current_agent = 'general'

# Main chat interface
st.title("Lead Capture Chat")

# Display chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# Display welcome message if it's a new session
if not st.session_state.messages:
    welcome_message = "How may I assist you today?" if st.session_state.current_agent == 'general' else "Before we begin, could you please provide your name?"
    st.chat_message("assistant").write(welcome_message)
    st.session_state.messages.append({"role": "assistant", "content": welcome_message})

# User input
user_input = st.chat_input("Type your message here...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.chat_message("user").write(user_input)
    st.session_state.message_count += 1

    # Process user input based on current agent
    if st.session_state.current_agent == 'general':
        if lead_capture_enabled and st.session_state.message_count >= messages_before_capture and not st.session_state.lead_captured:
            # Switch to lead capture agent
            st.session_state.current_agent = 'lead_capture'
            response = lead_capture_agent.chat(user_input)
        else:
            response = general_agent.chat(user_input)
    elif st.session_state.current_agent == 'lead_capture':
        response = lead_capture_agent.chat(user_input)
        
        # Check if lead info is captured
        listener_response = listener_agent.listen(user_input)
        if listener_response['verdict']:
            st.session_state.lead_info = {
                'name': listener_response['name'],
                'email': listener_response['email']
            }
            st.session_state.lead_captured = True
            st.session_state.current_agent = 'general'
            success_message = f"Lead captured: {st.session_state.lead_info['name']} ({st.session_state.lead_info['email']})"
            st.success(success_message)
            response += f"\n\n{success_message}\n\nHow else can I assist you today?"
    
    st.session_state.messages.append({"role": "assistant", "content": response})
    st.chat_message("assistant").write(response)

# Display current lead info
if st.session_state.lead_captured:
    st.sidebar.success(f"Lead captured: {st.session_state.lead_info['name']} ({st.session_state.lead_info['email']})")