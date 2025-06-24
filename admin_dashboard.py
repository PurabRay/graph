
import streamlit as st
from user_graph_db import (
    load_graph_from_db,
    persist_graph,
    Graph
)

def init_state():
    if "graph" not in st.session_state:
        st.session_state.graph = load_graph_from_db()

def sidebar_user_ui():
    g = st.session_state.graph
    st.sidebar.header("Add New User")
    uname = st.sidebar.text_input("Name", key="add_name")
    bio = st.sidebar.text_area("Bio", key="add_bio")
    tastes = st.sidebar.multiselect("Select ≥3 tastes", g.taste_list, key="add_tastes")
    if st.sidebar.button("Add User"):
        if not uname: st.sidebar.error("Name required")
        elif len(tastes)<3: st.sidebar.error("Select ≥3 tastes")
        else:
            g.add_user(uname,bio,tastes)
            st.sidebar.success("User added")
    st.sidebar.divider()
    users=list(g.adj)
    rem=st.sidebar.selectbox("Remove User",["-"]+users,key="rem_user")
    if st.sidebar.button("Remove",key="rem_btn") and rem!="-":
        g.remove_user(rem); st.sidebar.warning(f"Removed {rem}")

def sidebar_friendship_ui():
    g = st.session_state.graph
    st.sidebar.header("Friendships")
    users=list(g.adj)
    if len(users)<2:
        st.sidebar.info("Need ≥2 users"); return
    a=st.sidebar.selectbox("User A",users,key="fa")
    b=st.sidebar.selectbox("User B",users,key="fb")
    if st.sidebar.button("Add Friendship"):
        g.add_friendship(a,b); st.sidebar.success("Friend added")
    if st.sidebar.button("Remove Friendship"):
        g.remove_friendship(a,b); st.sidebar.warning("Friend removed")

def edit_profile_ui():
    g=st.session_state.graph
    st.header("Edit Profile")
    users=list(g.adj)
    if not users: st.info("No users"); return
    u=st.selectbox("Select User",users,key="edit_sel")
    p=g.get_profile(u)
    bio=st.text_area("Bio",value=p["bio"],key="edit_bio")
    tastes=st.multiselect("Tastes (≥3)",g.taste_list,default=p["tastes"],key="edit_tastes")
    if st.button("Update Profile"):
        if len(tastes)<3: st.error("Select ≥3 tastes")
        else:
            g.edit_profile(u,bio,tastes); st.success("Updated")

def analysis_ui():
    g=st.session_state.graph
    st.header("Network Analysis")
    users=list(g.adj)
    if not users: st.info("Add users"); return

    st.subheader("Shortest Path")
    if len(users)>=2:
        s=st.selectbox("Source",users,key="sp_src")
        d=st.selectbox("Dest",users,key="sp_dst")
        if st.button("Find Path"):
            p=g.bfs_shortest_path(s,d)
            p and st.success(" → ".join(p)) or st.error("No connection")

    st.subheader("Friend Recommendations")
    u=st.selectbox("User",users,key="rec_user")
    if st.button("Recommend"):
        recs=g.recommend_friends(u)
        if recs:
            lbl={2:"Cluster+FoF",1:"Cluster",0:"FoF"}
            st.table([(n,lbl[c],f"{s} shared") for n,c,s in recs])
        else: st.write("No recs")

    st.subheader("Cluster Mates")
    cm=sorted(g.users_in_same_taste_cluster(u))
    st.write(cm or "None")

    st.subheader("Mutual Friends")
    if len(users)>=2:
        x=st.selectbox("U1",users,key="mf_x")
        y=st.selectbox("U2",users,key="mf_y")
        if st.button("Find Mutual"):
            st.write(sorted(g.mutual_friends(x,y)))

    st.subheader("Popular Users")
    dg={u:len(g.adj[u]) for u in g.adj}
    st.table(sorted(dg.items(),key=lambda x:x[1],reverse=True)) if dg else st.write("None")

    st.subheader("Components")
    comps=g.connected_components()
    st.write(f"Total: {len(comps)}")
    for i,c in enumerate(comps,1):
        st.write(f"Comp {i}: {', '.join(sorted(c))}")

    st.subheader("Adjacency")
    st.json(g.adjacency_list())

    st.subheader("Profiles")
    for u in users:
        p=g.get_profile(u)
        st.markdown(f"**{u}**  \nBio: {p['bio']}  \nTastes: {', '.join(p['tastes']) or 'None'}")

def main():
    st.set_page_config(page_title="Admin Dashboard",layout="wide")
    init_state()
    g=st.session_state.graph
    st.title("Admin Dashboard")
    sidebar_user_ui()
    sidebar_friendship_ui()
    st.sidebar.button("Save Changes", on_click=lambda: persist_graph(g))
    st.write("---")
    edit_profile_ui()
    st.write("---")
    analysis_ui()

if __name__=="__main__":
    main()
