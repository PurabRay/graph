import streamlit as st
from pymongo import MongoClient


MONGO_URI = st.secrets["mongo_uri"]
client = MongoClient(MONGO_URI)
db = client["social_app"]

def main():
    st.set_page_config(page_title="Database State Viewer", layout="wide")
    st.title("Database Debug Panel")
    st.write("View all user profiles and friendships in your MongoDB.")

    # Profiles
    st.header("User Profiles")
    profiles = list(db["profiles"].find())
    st.json([{k: v for k, v in doc.items() if k != "_id"} for doc in profiles])

    # Friendships
    st.header("Friendships")
    friendships = list(db["friendships"].find())
    st.json([{k: v for k, v in doc.items() if k != "_id"} for doc in friendships])

    # Raw Documents
    with st.expander("Show raw documents (with _id field)"):
        st.subheader("Raw Profiles")
        st.write(profiles)
        st.subheader("Raw Friendships")
        st.write(friendships)

if __name__ == "__main__":
    main()
