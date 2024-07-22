import os
import streamlit as st
import boto3
import sqlite3
import pandas as pd
from ctransformers import AutoModelForCausalLM
import ctransformers  
from utils import get_timestamp, load_config, get_avatar
from database_operations import load_last_k_text_messages, save_text_message, load_messages, get_all_chat_history_ids, delete_chat_history
from html_templates import css

#st.write(f"ctransformers version: {ctransformers.__version__}")

config = load_config()

# DigitalOcean Spaces configuration
spaces_region = st.secrets["spaces"]["region"]
spaces_access_key = st.secrets["spaces"]["access_key"]
spaces_secret_key = st.secrets["spaces"]["secret_key"]
bucket_name = st.secrets["spaces"]["bucket_name"]
endpoint_url = f"https://{spaces_region}.digitaloceanspaces.com"

# Initialize Boto3 client
client = boto3.client(
    's3',
    region_name=spaces_region,
    aws_access_key_id=spaces_access_key,
    aws_secret_access_key=spaces_secret_key,
    endpoint_url=endpoint_url
)

# Define the paths to the models in your DigitalOcean Space
models = {
    "mistral-7b-instruct-v0.1.Q3_K_M.gguf": "models/mistral-7b-instruct-v0.1.Q3_K_M.gguf",
    "mistral-7b-instruct-v0.1.Q5_K_M.gguf": "models/mistral-7b-instruct-v0.1.Q5_K_M.gguf"
}

local_model_path = "./models"

def download_model(local_path, s3_key):
    if not os.path.exists(local_path):
        try:
            client.download_file(bucket_name, s3_key, local_path)
            st.write(f"Downloaded {os.path.basename(local_path)} successfully.")
        except Exception as e:
            st.error(f"Error downloading model: {e}")

# Download each model
for local_model, s3_key in models.items():
    local_path = os.path.join(local_model_path, local_model)
    download_model(local_path, s3_key)

@st.cache_resource
def load_model():
    model_path = os.path.join(local_model_path, "mistral-7b-instruct-v0.1.Q5_K_M.gguf")
    st.write(f"Attempting to load model from: {os.path.abspath(model_path)}")

    if not os.path.exists(model_path):
        st.error(f"Model file not found at {model_path}")
        return None
    try:
        model = AutoModelForCausalLM.from_pretrained(model_path, model_type="mistral")
        return model
    except Exception as e:
        st.error(f"Error loading model: {str(e)}")
        return None

model = load_model()

CONSULTANT_PROMPT = """
You are an AI business consultant from a top firm like Bain & Co, BCG, EY, PWC, or McKinsey. 
You specialize in creating great offers, price optimization, and product analysis. 
Use the following context to provide expert advice and recommendations:

{context}

Remember to:
1. Analyze the given information critically
2. Provide data-driven insights
3. Offer actionable recommendations
4. Use professional language typical of top consulting firms

Your response:
"""

def generate_consultant_response(context):
    if model is None:
        return "I apologize, but I'm having trouble accessing my knowledge. Please try again later."
    prompt = CONSULTANT_PROMPT.format(context=context)
    try:
        response = model(prompt, max_new_tokens=500, temperature=0.7, top_p=0.95)
        return response
    except Exception as e:
        st.error(f"Error generating response: {str(e)}")
        return "I'm sorry, but I encountered an error while processing your request. Please try again."

def get_session_key():
    if st.session_state.session_key == "new_session":
        st.session_state.new_session_key = get_timestamp()
        return st.session_state.new_session_key
    return st.session_state.session_key

def delete_chat_session_history():
    delete_chat_history(st.session_state.session_key)
    st.session_state.session_index_tracker = "new_session"

def clear_cache():
    st.cache_resource.clear()

def sign_up():
    st.title("Sign Up")
    
    name = st.text_input("Name", key="name_input")
    company_name = st.text_input("Company Name", key="company_input")
    email = st.text_input("Email", key="email_input")
    password = st.text_input("Password", type="password", key="password_input")
    confirm_password = st.text_input("Confirm Password", type="password", key="confirm_password_input")

    if st.button("Sign Up", key="signup_button"):
        if password == confirm_password:
            success = True  # Placeholder for actual implementation
            if success:
                st.success("You have successfully signed up!")
            else:
                st.error("Failed to sign up. Please try again.")
        else:
            st.error("Passwords do not match")

def sign_in():
    st.title("Sign In")
    
    email = st.text_input("Email", key="signin_email_input")
    password = st.text_input("Password", type="password", key="signin_password_input")

    if st.button("Sign In", key="signin_button"):
        authenticated = True  # Placeholder for actual implementation
        if authenticated:
            st.session_state.signed_in = True
            st.success("You have successfully signed in!")
            st.experimental_rerun()
        else:
            st.error("Failed to sign in. Please try again.")

def display_chat():
    st.markdown("<div class='chat-container'>", unsafe_allow_html=True)
    bot_avatar = "https://your-actual-space-url.digitaloceanspaces.com/chat_icons/pulsar.png"
    user_avatar = "https://your-actual-space-url.digitaloceanspaces.com/chat_icons/user.png"
    for message in st.session_state.chat_history:
        if message["sender"] == "user":
            st.markdown(f"<div class='chat-message user'><img src='{user_avatar}' alt='user' class='avatar' style='width:30px; height:30px; margin-right:10px;'/> {message['content']}</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='chat-message bot'><img src='{bot_avatar}' alt='bot' class='avatar' style='width:30px; height:30px; margin-right:10px;'/> {message['content']}</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

def handle_conversation(user_input):
    st.session_state.chat_history.append({"sender": "user", "content": user_input})
    display_chat()
    
    context = "\n".join([f"{msg['sender']}: {msg['content']}" for msg in st.session_state.chat_history[-5:]])
    response = generate_consultant_response(context + f"\nUser: {user_input}\nAI:")
    
    st.session_state.chat_history.append({"sender": "bot", "content": response})
    display_chat()

def analyze_csv_data(df):
    # Perform analysis on the DataFrame
    # This is a placeholder. You should implement actual analysis here.
    analysis = "Based on the CSV data provided, here are some initial insights:\n"
    analysis += f"1. The dataset contains {len(df)} records and {len(df.columns)} columns.\n"
    analysis += f"2. The average selling price is ${df['selling_price'].mean():.2f}.\n"
    analysis += "3. Further analysis is needed to provide specific recommendations."
    return analysis

def lead_conversation():
    if "user_data" not in st.session_state:
        st.session_state.user_data = {}

    if "conversation_step" not in st.session_state:
        st.session_state.conversation_step = 0

    bot_messages = [
        "Hello! How are you today?",
        "What is the name of your company?",
        "Could you please provide a brief about your business model?",
        "Please upload a CSV file containing the product IDs, names, cost price, selling price, competitor price if available, and history of sales if possible.",
        "What is your desired gross margin?",
        "Thank you! Let's proceed with the analysis."
    ]

    if st.session_state.conversation_step < len(bot_messages):
        if len(st.session_state.chat_history) == 0 or st.session_state.chat_history[-1]["sender"] != "bot":
            st.session_state.chat_history.append({"sender": "bot", "content": bot_messages[st.session_state.conversation_step]})
        
        display_chat()

        if st.session_state.conversation_step == 3:
            uploaded_file = st.file_uploader("Upload a CSV file", type=["csv"])
            if uploaded_file:
                df = pd.read_csv(uploaded_file)
                st.write("CSV file contents:")
                st.write(df)
                st.session_state.user_data['csv_data'] = df
                analysis_result = analyze_csv_data(df)
                st.session_state.chat_history.append({"sender": "bot", "content": analysis_result})
                st.session_state.conversation_step += 1
                st.experimental_rerun()
        else:
            user_input = st.text_input("Type your message here...", key=f"user_input_{st.session_state.conversation_step}")
            if user_input:
                handle_conversation(user_input)
                st.session_state.user_data[f'step_{st.session_state.conversation_step}'] = user_input
                st.session_state.conversation_step += 1
                st.experimental_rerun()
    else:
        display_chat()
        user_input = st.text_input("Type your message here...", key="user_input")
        if user_input:
            handle_conversation(user_input)
            st.experimental_rerun()

def main():
    st.title("Pulsar Apps Assistant")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    
    if "db_conn" not in st.session_state:
        st.session_state.session_key = "new_session"
        st.session_state.new_session_key = None
        st.session_state.session_index_tracker = "new_session"
        st.session_state.db_conn = sqlite3.connect(config["chat_sessions_database_path"], check_same_thread=False)
        st.session_state.signed_in = False
    
    if st.session_state.session_key == "new_session" and st.session_state.new_session_key is not None:
        st.session_state.session_index_tracker = st.session_state.new_session_key
        st.session_state.new_session_key = None

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    if st.session_state.signed_in:
        if "conversation_step" not in st.session_state or st.session_state.conversation_step < 6:
            lead_conversation()
        else:
            display_chat()
            user_input = st.text_input("Type your message here...", key="user_input")
            if user_input:
                handle_conversation(user_input)
                st.experimental_rerun()
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