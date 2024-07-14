import streamlit as st
from llm_chains import load_normal_chain
from utils import get_timestamp, load_config, get_avatar
from image_handler import handle_image
from database_operations import load_last_k_text_messages, save_text_message, save_image_message, load_messages, get_all_chat_history_ids, delete_chat_history
import sqlite3
import pandas as pd
from sqlalchemy import create_engine
import pymongo
#import ShopifyAPI 
import simple_salesforce

__import__('pysqlite3')
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
config = load_config()

@st.cache_resource
def load_chain():
    return load_normal_chain()

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

def upload_csv():
    uploaded_file = st.file_uploader("Upload a CSV file", type=["csv"])
    if uploaded_file:
        data = pd.read_csv(uploaded_file)
        st.write(data)
        return data
    return None

def connect_sql_db(connection_string):
    engine = create_engine(connection_string)
    return engine

def connect_mongo_db(connection_string):
    client = pymongo.MongoClient(connection_string)
    return client

#def connect_shopify(api_key, password, store_name):
 #   shop_url = f"https://{api_key}:{password}@{store_name}.myshopify.com/admin"
  #  shopify.ShopifyResource.set_site(shop_url)
   # return shopify

def connect_salesforce(username, password, security_token):
    sf = simple_salesforce.Salesforce(username=username, password=password, security_token=security_token)
    return sf

def analyze_sales(data):
    most_sold_product = data['Product'].value_counts().idxmax()
    highest_margin_product = (data['Revenue'] - data['Cost']).idxmax()
    most_revenue_product = data.groupby('Product')['Revenue'].sum().idxmax()
    most_profitable_product = (data.groupby('Product')['Revenue'].sum() - data.groupby('Product')['Cost'].sum()).idxmax()

    report = {
        "most_sold_product": most_sold_product,
        "highest_margin_product": highest_margin_product,
        "most_revenue_product": most_revenue_product,
        "most_profitable_product": most_profitable_product
    }

    return report

def lead_conversation():
    st.session_state.conversation_step = st.session_state.get('conversation_step', 0)

    if st.session_state.conversation_step == 0:
        st.chat_message("bot", "Hello! How are you today?")
        st.session_state.conversation_step += 1
        return

    user_input = st.chat_input("Type your message here", key="user_input")

    if st.session_state.conversation_step == 1:
        if user_input:
            st.chat_message("user", user_input)
            st.chat_message("bot", "Great! What's the name of your company?")
            st.session_state.conversation_step += 1
            st.session_state.user_input = ""
        return

    if st.session_state.conversation_step == 2:
        if user_input:
            st.chat_message("user", user_input)
            st.chat_message("bot", "Can you give me a brief about your company and business model?")
            st.session_state.company_name = user_input
            st.session_state.conversation_step += 1
            st.session_state.user_input = ""
        return

    if st.session_state.conversation_step == 3:
        if user_input:
            st.chat_message("user", user_input)
            st.chat_message("bot", "Thank you! What are you looking for today? Better offers, price optimization, or just analytics and recommendations?")
            st.session_state.company_brief = user_input
            st.session_state.conversation_step += 1
            st.session_state.user_input = ""
        return

    if st.session_state.conversation_step == 4:
        if user_input:
            st.chat_message("user", user_input)
            if "better offers" in user_input.lower():
                st.chat_message("bot", "Great! Please upload your product data in a CSV file.")
                st.session_state.user_request = "better offers"
            elif "price optimization" in user_input.lower():
                st.chat_message("bot", "Great! Please upload your product data in a CSV file.")
                st.session_state.user_request = "price optimization"
            elif "analytics" in user_input.lower():
                st.chat_message("bot", "Great! Please upload your product data in a CSV file.")
                st.session_state.user_request = "analytics"
            st.session_state.conversation_step += 1
            st.session_state.user_input = ""
        return

    if st.session_state.conversation_step == 5:
        data = upload_csv()
        if data is not None:
            if st.session_state.user_request == "analytics":
                report = analyze_sales(data)
                st.chat_message("bot", f"Here is your sales analysis report: {report}")
            # Additional logic for better offers and price optimization can be added here
        return

def main():
    st.title("Pulsar Apps Assistant")
    st.write(css, unsafe_allow_html=True)
    
    if "db_conn" not in st.session_state:
        st.session_state.session_key = "new_session"
        st.session_state.new_session_key = None
        st.session_state.session_index_tracker = "new_session"
        st.session_state.db_conn = sqlite3.connect(config["chat_sessions_database_path"], check_same_thread=False)
        st.session_state.audio_uploader_key = 0
        st.session_state.pdf_uploader_key = 1
        st.session_state.conversation_step = 0

    st.sidebar.title("Chat Sessions")
    chat_sessions = ["new_session"] + get_all_chat_history_ids()
    index = chat_sessions.index(st.session_state.session_index_tracker)
    st.sidebar.selectbox("Select a chat session", chat_sessions, key="session_key", index=index)
    delete_chat_col, clear_cache_col = st.sidebar.columns(2)
    delete_chat_col.button("Delete Chat Session", on_click=delete_chat_session_history)
    clear_cache_col.button("Clear Cache", on_click=clear_cache)
    
    chat_container = st.container()
    lead_conversation()
    
    if (st.session_state.session_key != "new_session") != (st.session_state.new_session_key != None):
        with chat_container:
            chat_history_messages = load_messages(get_session_key())

            for message in chat_history_messages:
                with st.chat_message(name=message["sender_type"], avatar=get_avatar(message["sender_type"])):
                    if message["message_type"] == "text":
                        st.write(message["content"])
                    if message["message_type"] == "image":
                        st.image(message["content"])
                    if message["message_type"] == "audio":
                        st.audio(message["content"], format="audio/wav")

        if (st.session_state.session_key == "new_session") and (st.session_state.new_session_key != None):
            st.rerun()

if __name__ == "__main__":
    main()
