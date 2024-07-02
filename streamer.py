import streamlit as st
import re
import json
import uuid
from customgpt_client import CustomGPT
from openai import OpenAI

# Function to retrieve citations using CustomGPT API
def get_citations(api_token, project_id, citation_id):
    CustomGPT.api_key = api_token
    try:
        response_citations = CustomGPT.Citation.get(project_id=project_id, citation_id=citation_id)
        if response_citations.status_code == 200:
            citation = response_citations.parsed.data
            if citation.url is not None:
                source = {'title': citation.title, 'url': citation.url}
            else:
                source = {'title': 'source', 'url': ""}
            return source
        else:
            return []
    except Exception as e:
        print(f"error::{e}")

# Function to query the chatbot using CustomGPT API
def query_chatbot(api_token, project_id, session_id, message, stream=True, lang='en'):
    CustomGPT.api_key = api_token
    try:
        stream_response = CustomGPT.Conversation.send(project_id=project_id, session_id=session_id, prompt=message, stream=stream, lang=lang)
        return stream_response
    except Exception as e:
        return [f"Error:: {e}"]

# Function to get the list of projects using CustomGPT API
def get_project_list(api_token):
    CustomGPT.api_key = api_token
    try:
        projects = CustomGPT.Project.list()
        if projects.status_code == 200:
            return projects.parsed.data.data
        else:
            return []
    except Exception as e:
        print(f"error:get_project_list:: {e}")

# Function to clear chat history
def clear_chat_history():
    st.session_state.session_id = str(uuid.uuid4())
    st.session_state.messages = [{"role": "assistant", "content": "How may I assist you today?"}]
    st.session_state.init = True

# Function to load prompt for Listener
def load_prompt(file_path):
    try:
        with open(file_path, 'r') as file:
            return file.read()
    except FileNotFoundError:
        print("The specified file was not found.")
        return ""

# Listener class for capturing leads
class Listener:
    def __init__(self, api_key):
        self.client = OpenAI(api_key=api_key)
        self.system_prompt = load_prompt("listener.txt") 
        if 'custom_message' in st.session_state:
            self.system_prompt += f"\n\n{st.session_state.custom_message}"

    def listen(self, query):
        conversation_history = [{"role": "system", "content": self.system_prompt}] + \
                               st.session_state.messages + \
                               [{"role": "user", "content": query}]
        response = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            response_format={"type": "json_object"},
            messages=conversation_history,
            max_tokens=4096
        )
        return response.choices[0].message.content
    
    def extract_response(response):
        pattern = r"```[\w]*\n([\s\S]*?)```"
        match = re.search(pattern, response)
        if match:
            return match.group(1).strip()
        else:
            return response
    
    def extract_verdict(self, response):
        try:
            response_json = json.loads(response)
            if 'verdict' in response_json and response_json['verdict'] is not None:
                return response_json.get('verdict')
        except json.JSONDecodeError:
            return None
        except TypeError as e:
            return None

# Initialize listener
openai_api_key = st.secrets["OPENAI_API_KEY"]
listener = Listener(openai_api_key)

# App title
st.set_page_config(page_title="CustomGPT Chatbot")

# Ensure session state initialization happens once
if "init" not in st.session_state:
    st.session_state.init = True
    st.session_state.session_id = str(uuid.uuid4())
    st.session_state.messages = [{"role": "assistant", "content": "How may I assist you today?"}]
    st.session_state.append_after = 3  # Set the threshold to 3
    st.session_state.custom_message = ""
    st.session_state.append_enabled = False
    st.session_state.disable_chat = False
    st.session_state.info = False
    st.session_state.append_custom_message = False
    st.session_state.user_info = {}
    st.session_state.disable_chat_input = False
    st.session_state.message_count = 0

# CustomGPT Credentials
with st.sidebar:
    st.title('CustomGPT Streamlit Demo')
    st.markdown("Don't have an API key? Get one [here](https://docs.customgpt.ai/reference/i-api-homepage).")
    customgpt_api_key = st.text_input('Enter CustomGPT API Key:', type='password')
    if customgpt_api_key:
        st.subheader('Select Project')
        list_project = get_project_list(customgpt_api_key)
        
        if list_project is not None:
            project_names = [projt.project_name for projt in list_project]
            selected_model = st.sidebar.selectbox('Select Model', project_names, key='selected_model')
            index = project_names.index(selected_model)
            selected_project = list_project[index]
        else:
            st.error('No projects found. Please check your API key.', icon='❌')

        st.sidebar.button('Reset Chat', on_click=clear_chat_history)
        st.session_state.append_enabled = st.sidebar.checkbox("Enable custom message appending", value=st.session_state.append_enabled)
        
        if st.session_state.append_enabled:
            st.session_state.custom_message = st.text_input("Custom message to append:", value=st.session_state.custom_message)
            st.session_state.disable_chat = st.checkbox("Disable chat after appending message", value=st.session_state.disable_chat)
            st.session_state.append_after = st.number_input("Append after how many messages?", min_value=0, value=st.session_state.append_after)
                

# Display or clear chat messages
for index, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        st.write(f"{message['content']}")
st.session_state.message_count = len([msg for msg in st.session_state.messages if msg["role"] == "assistant"])

# User-provided prompt
if st.session_state.info and st.session_state.disable_chat_input:
    prompt = st.chat_input(disabled=True, key="user_input")
elif not st.session_state.get('disable_chat_input', False):
    prompt = st.chat_input(disabled=not customgpt_api_key, key="user_input")
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        #Debug
        with st.chat_message("user"):
            st.write(prompt)
        #End Debug
        if st.session_state.info != True:
            verdict = listener.extract_verdict(listener.listen(prompt))
            #Debug
            with st.chat_message("assistant"):
                st.write(verdict)
                st.write(listener.listen(prompt))
            #end debug
            if verdict:
                st.session_state.info = True
                thankyou='Thank you!'
                st.session_state.messages.append({"role": "assistant", "content": thankyou})
                with st.chat_message("assistant"):
                    st.write(thankyou)
                    st.write(st.session_state.messages[-4]["content"])

# Generate a new response if the last message is not from the assistant
if st.session_state.messages[-1]["role"] != "assistant":
    if st.session_state.disable_chat and st.session_state.message_count >= st.session_state.append_after and not st.session_state.info:
        st.session_state.messages.append({"role": "assistant", "content": st.session_state.custom_message})
        with st.chat_message("assistant"):
            st.write(st.session_state.custom_message)
    elif st.session_state.disable_chat and st.session_state.message_count >= st.session_state.append_after and st.session_state.info:
        st.session_state.disable_chat_input = True
    else:
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                client = query_chatbot(customgpt_api_key, selected_project['id'], st.session_state.session_id, prompt)
                placeholder = st.empty()
                full_response = ""
                
                for event in client.events():
                    resp_data = eval(event.data.replace('null', 'None'))
                    
                    if resp_data is not None:
                        if resp_data.get('status') == 'error':
                            full_response += resp_data.get('message', '')
                            placeholder.markdown(full_response + "▌")

                        if resp_data.get('status') == 'progress':
                            full_response += resp_data.get('message', '')
                            placeholder.markdown(full_response + "▌")

                        if resp_data.get('status') == 'finish' and resp_data.get('citations') is not None:
                            citation_ids = resp_data.get('citations', [])
                            citation_links = []
                            count = 1
                            
                            for citation_id in citation_ids:
                                citation_obj = get_citations(customgpt_api_key, selected_project['id'], citation_id)
                                url = citation_obj.get('url', '')
                                title = citation_obj.get('title', '')
                                
                                if len(url) > 0:
                                    formatted_url = f"{count}. [{title or url}]({url})"
                                    count += 1
                                    citation_links.append(formatted_url)

                            if citation_links:
                                cita = "\n\nSources:\n"
                                for link in citation_links:
                                    cita += f"{link}\n"
                                full_response += cita
                                placeholder.markdown(full_response + "▌")
                            
                placeholder.markdown(full_response)
                
        if full_response == "":
            full_response = "Oh no! An unknown error has occurred. Please check your CustomGPT Dashboard for details."
            placeholder.markdown(full_response)
        
        message = {"role": "assistant", "content": full_response}
        st.session_state.messages.append(message)
        st.session_state.message_count += 1

        # Append custom message conditionally
        if st.session_state.append_enabled:
            if st.session_state.message_count >= st.session_state.append_after and not st.session_state.info:
                st.session_state.append_custom_message = True  # Set the flag after the threshold is reached
            if st.session_state.info:
                st.session_state.append_custom_message = False
            if st.session_state.append_custom_message:
                st.session_state.messages.append({"role": "assistant", "content": st.session_state.custom_message})
                with st.chat_message("assistant"):
                    st.write(st.session_state.custom_message)
                    st.write(st.session_state.info)
                if st.session_state.disable_chat and st.session_state.info:
                    st.session_state.disable_chat_input = True
