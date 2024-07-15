import os
import streamlit as st
import boto3
import sqlite3
import pandas as pd
from llm_chains import load_normal_chain, load_pdf_chat_chain
from streamlit_mic_recorder import mic_recorder
from utils import get_timestamp, load_config, get_avatar
from image_handler import handle_image
from audio_handler import transcribe_audio
from pdf_handler import add_documents_to_db
from html_templates import css
from database_operations import load_last_k_text_messages, save_text_message, save_image_message, save_audio_message, load_messages, get_all_chat_history_ids, delete_chat_history

config = load_config()

# DigitalOcean Spaces configuration
spaces_region = st.secrets["spaces"]["region"]
spaces_access_key = st.secrets["spaces"]["access_key"]
spaces_secret_key = st.secrets["spaces"]["secret_key"]
bucket_name = st.secrets["spaces"]["bucket_name"]
endpoint_url = f"https://{spaces_region}.digitaloceanspaces.com"

# Initialize Boto3 client with the correct endpoint URL
client = boto3.client(
    's3',
    region_name=spaces_region,
    aws_access_key_id=spaces_access_key,
    aws_secret_access_key=spaces_secret_key,
    endpoint_url=endpoint_url
)

# Define the paths to the models in your DigitalOcean Space
models = {
    "mistral-7b-instruct-v0.1.Q3_K_M.gguf": "mistral-7b-instruct-v0.1.Q3_K_M.gguf",
    "mistral-7b-instruct-v0.1.Q5_K_M.gguf": "mistral-7b-instruct-v0.1.Q5_K_M.gguf"
}

local_model_path = "./models"

# Function to download a model if it does not exist locally
def download_model(local_path, s3_key):
    if not os.path.exists(local_path):
        try:
            client.download_file(bucket_name, s3_key, local_path)
            st.write(f"Downloaded {os.path.basename(local_path)} successfully.")
        except client.exceptions.NoSuchKey:
            st.error(f"Model {s3_key} not found in bucket {bucket_name}. Please check the path and try again.")
        except Exception as e:
            st.error(f"Error downloading model: {e}")
    

# Download each model
for local_model, s3_key in models.items():
    local_path = os.path.join(local_model_path, local_model)
    download_model(local_path, s3_key)

@st.cache_resource
def load_chain():
    """Load the appropriate language model chain based on the chat type."""
    #if st.session_state.pdf_chat:
     #   print("loading pdf chat chain")
      #  return load_pdf_chat_chain()
    return load_normal_chain()

def toggle_pdf_chat():
    """Toggle the state to indicate whether PDF chat is enabled."""
    st.session_state.pdf_chat = True
    clear_cache()

def get_session_key():
    """Get the current session key, generate a new one if it's a new session."""
    if st.session_state.session_key == "new_session":
        st.session_state.new_session_key = get_timestamp()
        return st.session_state.new_session_key
    return st.session_state.session_key

def delete_chat_session_history():
    """Delete the current chat session history from the database."""
    delete_chat_history(st.session_state.session_key)
    st.session_state.session_index_tracker = "new_session"

def clear_cache():
    """Clear the Streamlit cache."""
    st.cache_resource.clear()

def sign_up():
    """Render the sign-up form and handle user registration."""
    st.title("Sign Up")
    
    name = st.text_input("Name", key="name_input")
    company_name = st.text_input("Company Name", key="company_input")
    email = st.text_input("Email", key="email_input")
    password = st.text_input("Password", type="password", key="password_input")
    confirm_password = st.text_input("Confirm Password", type="password", key="confirm_password_input")

    if st.button("Sign Up", key="signup_button"):
        if password == confirm_password:
            # Call backend to create a new user (Example function)
            # success = create_new_user(name, company_name, email, password)
            success = True  # Placeholder for actual implementation
            if success:
                st.success("You have successfully signed up!")
            else:
                st.error("Failed to sign up. Please try again.")
        else:
            st.error("Passwords do not match")

def sign_in():
    """Render the sign-in form and handle user authentication."""
    st.title("Sign In")
    
    email = st.text_input("Email", key="signin_email_input")
    password = st.text_input("Password", type="password", key="signin_password_input")

    if st.button("Sign In", key="signin_button"):
        # Call backend to authenticate user (Example function)
        # authenticated = authenticate_user(email, password)
        authenticated = True  # Placeholder for actual implementation
        if authenticated:
            st.session_state.signed_in = True
            st.success("You have successfully signed in!")
            st.experimental_rerun()
        else:
            st.error("Failed to sign in. Please try again.")

def display_chat():
    """Display the chat history."""
    st.markdown("<div class='chat-container'>", unsafe_allow_html=True)
    bot_avatar = os.path.join("chat_icons", "pulsar.png")
    for message in st.session_state.chat_history:
        if message["sender"] == "user":
            st.markdown(f"<div class='chat-message user'>{message['content']}</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='chat-message bot'><img src='{bot_avatar}' alt='bot' class='avatar'/> {message['content']}</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

def handle_conversation():
    """Handle the conversation flow based on user input."""
    user_input = st.session_state.user_input
    if user_input:
        st.chat_message("user").write(user_input)
        st.session_state.chat_history.append({"sender": "user", "content": user_input})
        llm_chain = load_chain()
        llm_answer = llm_chain.run(user_input=user_input, chat_history=load_last_k_text_messages(get_session_key(), config["chat_config"]["chat_memory_length"]))
        st.chat_message("bot").write(llm_answer)
        st.session_state.chat_history.append({"sender": "bot", "content": llm_answer})


def main():
    """Main function to render the Streamlit app."""
    st.title("Pulsar Apps Assistant")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    
    if "db_conn" not in st.session_state:
        st.session_state.session_key = "new_session"
        st.session_state.new_session_key = None
        st.session_state.session_index_tracker = "new_session"
        st.session_state.db_conn = sqlite3.connect(config["chat_sessions_database_path"], check_same_thread=False)
        st.session_state.audio_uploader_key = 0
        st.session_state.pdf_uploader_key = 1
        st.session_state.signed_in = False
    
    if st.session_state.session_key == "new_session" and st.session_state.new_session_key is not None:
        st.session_state.session_index_tracker = st.session_state.new_session_key
        st.session_state.new_session_key = None

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    if "conversation_stage" not in st.session_state:
        st.session_state.conversation_stage = "greeting"

    if st.session_state.signed_in:
        display_chat()
        user_input = st.chat_input("Type your message here...")
        if user_input:
            st.session_state.user_input = user_input
            handle_conversation()
            st.experimental_rerun()
            
        uploaded_file = st.file_uploader("Upload a CSV file", type=["csv"])
        if uploaded_file:
            df = pd.read_csv(uploaded_file)
            st.write("CSV file contents:")
            st.write(df)
            # You can add logic to analyze the CSV file here    
    else:
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Sign In", key="nav_signin_button"):
                st.session_state.nav_mode = "Sign In"
        with col2:
            if st.button("Sign Up", key="nav_signup_button"):
                st.session_state.nav_mode = "Sign Up"
        
        if "nav_mode" in st.session_state:
            if st.session_state.nav_mode == "Sign In":
                sign_in()
            elif st.session_state.nav_mode == "Sign Up":
                sign_up()

if __name__ == "__main__":
    main()
