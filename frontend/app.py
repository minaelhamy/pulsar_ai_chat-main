import os
import streamlit as st
import boto3
import sqlite3
import pandas as pd
import PyPDF2
from ctransformers import AutoModelForCausalLM
import ctransformers  
from utils import get_timestamp, load_config, get_avatar
from database_operations import load_last_k_text_messages, save_text_message, load_messages, get_all_chat_history_ids, delete_chat_history
from html_templates import css


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
    if not os.path.exists(model_path):
        st.error(f"Model file not found at {model_path}")
        return None
    try:
        # Load the model for CPU operation
        model = AutoModelForCausalLM.from_pretrained(model_path, model_type="mistral", gpu_layers=0)
        st.success("Model loaded successfully on CPU.")
    except Exception as e:
        st.error(f"Error loading model: {str(e)}")
        return None
    return model

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

@st.cache_data
def analyze_csv(df):
    analysis = "Based on the CSV data provided, here are some initial insights:\n"
    analysis += f"1. The dataset contains {len(df)} records and {len(df.columns)} columns.\n"
    analysis += f"2. Columns present: {', '.join(df.columns)}\n"
    analysis += f"3. Sample data:\n{df.head().to_string()}\n"
    analysis += "4. Further analysis and recommendations would require more context about your specific business needs."
    return analysis

@st.cache_data
def analyze_pdf(pdf_content):
    analysis = "Based on the PDF content provided, here are some initial insights:\n"
    analysis += f"1. The PDF contains {len(pdf_content.split())} words.\n"
    analysis += f"2. Key topics might include: [List some key topics or frequent words]\n"
    analysis += "3. For a more detailed analysis and recommendations, please provide specific questions or areas of interest related to this document."
    return analysis

def handle_file_upload():
    uploaded_file = st.file_uploader("Upload a CSV or PDF file", type=["csv", "pdf"])
    if uploaded_file is not None:
        file_extension = uploaded_file.name.split(".")[-1].lower()
        if file_extension == "csv":
            df = pd.read_csv(uploaded_file)
            analysis = analyze_csv(df)
        elif file_extension == "pdf":
            pdf_reader = PyPDF2.PdfReader(uploaded_file)
            pdf_content = ""
            for page in pdf_reader.pages:
                pdf_content += page.extract_text()
            analysis = analyze_pdf(pdf_content)
        
        st.session_state.chat_history.append({"sender": "bot", "content": analysis})
        display_chat()

def generate_consultant_response(context):
    if model is None:
        return "I apologize, but I'm having trouble accessing my knowledge. Please try again later."
    prompt = CONSULTANT_PROMPT.format(context=context)
    try:
        with st.spinner("Generating response..."):
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
    bot_avatar = "https://pulsarchatmodel.ams3.cdn.digitaloceanspaces.com/AoGxnGDP6zpvk6if7CoQ4N-1200-80.jpg"
    user_avatar = "https://pulsarchatmodel.ams3.cdn.digitaloceanspaces.com/anonymous-user-circle-icon-vector-illustration-flat-style-with-long-shadow_520826-1931.png"
    for message in st.session_state.chat_history:
        if message["sender"] == "user":
            st.markdown(f"<div class='chat-message user'><img src='{user_avatar}' alt='user' class='avatar' style='width:30px; height:30px; margin-right:10px;'/> {message['content']}</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='chat-message bot'><img src='{bot_avatar}' alt='bot' class='avatar' style='width:30px; height:30px; margin-right:10px;'/> {message['content']}</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

@st.cache_data
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


def handle_conversation(user_input):
    st.session_state.chat_history.append({"sender": "user", "content": user_input})
    
    context = "\n".join([f"{msg['sender']}: {msg['content']}" for msg in st.session_state.chat_history[-5:]])
    response = generate_consultant_response(context + f"\nUser: {user_input}\nAI:")
    
    st.session_state.chat_history.append({"sender": "bot", "content": response})


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
        if not st.session_state.chat_history:
            st.session_state.chat_history.append({"sender": "bot", "content": "How can I help you today?"})
        
        display_chat()
        
        # File upload option
        handle_file_upload()
        
        user_input = st.text_input("Type your message here...", key="user_input")
        if user_input:
            with st.spinner("Processing your request..."):
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