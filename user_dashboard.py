import streamlit as st
from user_graph_db import load_graph_from_db, persist_graph

st.set_page_config(page_title="User Dashboard", layout="wide")

def main():
    # 1) Restore login from URL
    params = st.query_params
    if "user" in params and "user" not in st.session_state:
        raw = params["user"]
        st.session_state["user"] = raw[-1] if isinstance(raw, list) else raw

    # 2) Load graph
    g = load_graph_from_db()
    users = sorted(g.adj.keys())

    # 3) Login / Sign Up
    if "user" not in st.session_state:
        st.title("Welcome to the User Dashboard")
        mode = st.radio("Choose mode", ["Login", "Sign Up"])
        if mode == "Login":
            st.header("Login")
            username = st.selectbox("Username", users) if users else st.text_input("Username")
            password = st.text_input("Password", type="password")
            if st.button("Login"):
                prof = g.get_profile(username)
                if not prof:
                    st.error("User not found.")
                elif prof.get("password", "") != password:
                    st.error("Incorrect password.")
                else:
                    st.session_state["user"] = username
                    st.query_params["user"] = username
                    st.success(f"Logged in as {username}")
        else:
            st.header("Sign Up")
            username     = st.text_input("Choose a username")
            password     = st.text_input("Set a password", type="password")
            bio          = st.text_area("Bio")
            tastes       = st.multiselect("Select at least 3 tastes", g.taste_list)
            avatar_upload = st.file_uploader("Profile picture (png/jpg)", type=["png","jpg","jpeg"])
            if st.button("Sign Up"):
                if not username or not password:
                    st.error("Username and password required.")
                elif len(tastes) < 3:
                    st.error("Please select at least 3 tastes.")
                elif username in users:
                    st.error("Username already taken.")
                else:
                    avatar_bytes = avatar_upload.read() if avatar_upload else None
                    g.add_user(username, bio, tastes, password=password, avatar=avatar_bytes)
                    persist_graph(g)
                    st.session_state["user"] = username
                    st.query_params["user"] = username
                    st.success("Signed up successfully.")
        return  # don’t render the rest until logged in

    # 4) Main Dashboard
    user = st.session_state["user"]
    st.title(f"Welcome, {user}!")

    # Log out
    if st.button("Log out"):
        del st.session_state["user"]
        st.query_params.clear()
        st.success("Logged out successfully")
        return

    # Show avatar if present
    prof = g.get_profile(user)
    if prof.get("avatar"):
        st.image(prof["avatar"], width=150)

    # Your Friends (hidden until expanded)
    with st.expander("Your Friends"):
        friends = sorted(g.adj.get(user, set()))
        if friends:
            for f in friends:
                c1, c2 = st.columns([3,1])
                c1.write(f)
                if c2.button("Remove", key=f"rm_{f}"):
                    g.remove_friendship(user, f)
                    persist_graph(g)
                    st.experimental_rerun()
        else:
            st.write("You have no friends yet.")

    # Incoming Friend Requests
    st.subheader("Incoming Friend Requests")
    incoming = g.get_incoming_requests(user)
    if incoming:
        for sender in incoming:
            c1, c2, c3 = st.columns([3,1,1])
            c1.write(sender)
            if c2.button("Accept", key=f"ac_{sender}"):
                g.accept_friend_request(sender, user)
                persist_graph(g)
                st.success(f"You are now friends with {sender}")
                st.experimental_rerun()
            if c3.button("Reject", key=f"rj_{sender}"):
                g.reject_friend_request(sender, user)
                persist_graph(g)
                st.info(f"Rejected request from {sender}")
                st.experimental_rerun()
    else:
        st.write("No incoming requests.")

    # Friend Recommendations
    st.subheader("Friend Recommendations")
    recs = g.recommend_friends(user)
    if recs:
        labels = {2: "Cluster + FoF", 1: "Cluster", 0: "Friends-of-Friends"}
        for name, code, shared in recs:
            exp = st.expander(f"{name} — {shared} shared tastes ({labels[code]})")
            with exp:
                p = g.get_profile(name)
                if p.get("avatar"):
                    st.image(p["avatar"], width=100)
                st.write("**Bio:**", p.get("bio",""))
                st.write("**Tastes:**", ", ".join(p.get("tastes",[])))
                if st.button("Send Request", key=f"sr_{name}"):
                    g.send_friend_request(user, name)
                    persist_graph(g)
                    st.success(f"Friend request sent to {name}")
    else:
        st.write("No recommendations at this time.")

    # People in Your Network (FoF)
    st.subheader("People in Your Network")
    fof = set()
    for f in g.adj.get(user, set()):
        fof |= g.adj.get(f, set())
    fof.discard(user)
    fof -= g.adj.get(user, set())

    if fof:
        for person in sorted(fof):
            exp = st.expander(person)
            with exp:
                p = g.get_profile(person)
                if p.get("avatar"):
                    st.image(p["avatar"], width=100)
                st.write("**Bio:**", p.get("bio",""))
                st.write("**Tastes:**", ", ".join(p.get("tastes",[])))
                c1, c2 = st.columns(2)
                if c1.button("Show relation path", key=f"path_{person}"):
                    path = g.bfs_shortest_path(user, person)
                    st.info(" → ".join(path) if path else "No path found")
                if person not in g.adj.get(user, set()) \
                   and user not in g.pending_requests.get(person, set()):
                    if c2.button("Send Request", key=f"net_{person}"):
                        g.send_friend_request(user, person)
                        persist_graph(g)
                        st.success(f"Friend request sent to {person}")
    else:
        st.write("No one in your network beyond your friends.")

    # --- New: Check Mutual Friends ---
    st.subheader("Check Mutual Friends")
    friends = sorted(g.adj.get(user, set()))
    if friends:
        friend_sel = st.selectbox("Select a friend to compare", friends, key="mf_friend")
        if st.button("Show Mutual Friends"):
            mutual = sorted(g.mutual_friends(user, friend_sel))
            if mutual:
                st.write(", ".join(mutual))
            else:
                st.write("No mutual friends with", friend_sel)
    else:
        st.write("You have no friends to compare mutuals with.")

    # --- New: Popular Users (Most Friends) ---
    st.subheader("Popular Users")
    degrees = {u: len(g.adj.get(u, set())) for u in users}
    if degrees:
        popular = sorted(degrees.items(), key=lambda x: x[1], reverse=True)
        st.table(popular)
    else:
        st.write("No users in the network yet.")

if __name__ == "__main__":
    main()
