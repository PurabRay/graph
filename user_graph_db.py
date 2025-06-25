

import streamlit as st
from pymongo import MongoClient
from typing import List, Set, Dict, Optional

#MongoDB Setup via Streamlit Secrets
MONGO_URI    = st.secrets["mongo_uri"]
client       = MongoClient(MONGO_URI)
db           = client["social_app"]
profiles_col = db["profiles"]        # { username, bio, tastes:list[str], password, avatar: bytes }
friends_col  = db["friendships"]     # { username, friends:list[str] }
requests_col = db["friend_requests"] # { username, requests:list[str] }

#DSU for Taste Clusters
class DSU:
    def __init__(self):
        self.parent: Dict[str, str] = {}

    def find(self, x: str) -> str:
        if x not in self.parent:
            self.parent[x] = x
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, x: str, y: str):
        rx, ry = self.find(x), self.find(y)
        if rx != ry:
            self.parent[rx] = ry

    def cluster_members(self, taste_list: List[str]) -> Set[str]:
        roots = {self.find(t) for t in taste_list}
        return {t for t in self.parent if self.find(t) in roots}

#In-memory Graph + Persistence Logic
class Graph:
    def __init__(self):
        self.adj: Dict[str, Set[str]]      = {}
        self.profile: Dict[str, Dict]      = {}
        self.pending_requests: Dict[str, Set[str]] = {}
        self.taste_list = [
            "Rock Music", "Classical Music", "Hip-Hop", "Jazz",
            "Football", "Basketball", "Cricket", "Badminton",
            "Science Fiction", "Fantasy", "Mystery", "Romance",
            "Coding", "Gaming", "Cooking", "Travel"
        ]
        self.taste_dsu = DSU()

    #rebuild DSU whenever profiles change
    def _rebuild_taste_dsu(self):
        self.taste_dsu = DSU()
        for t in self.taste_list:
            self.taste_dsu.find(t)
        for p in self.profile.values():
            ts = p.get("tastes", [])
            for i in range(1, len(ts)):
                self.taste_dsu.union(ts[0], ts[i])

    def users_in_same_taste_cluster(self, user: str) -> Set[str]:
        if user not in self.profile:
            return set()
        ut = self.profile[user].get("tastes", [])
        if not ut:
            return set()
        ct = self.taste_dsu.cluster_members(ut)
        return {
            other
            for other, pdata in self.profile.items()
            if other != user and set(pdata.get("tastes", [])) & ct
        }

    #CRUD & Avatars
    def add_user(self,
                 user: str,
                 bio: str,
                 tastes: List[str],
                 password: str = "",
                 avatar: Optional[bytes] = None):
        user = user.strip()
        if not user or user in self.adj:
            return
        self.adj[user] = set()
        self.profile[user] = {
            "bio": bio,
            "tastes": tastes,
            "password": password,
            "avatar": avatar
        }
        self.pending_requests.setdefault(user, set())
        self._rebuild_taste_dsu()

    def edit_profile(self,
                     user: str,
                     bio: str,
                     tastes: List[str],
                     password: Optional[str] = None,
                     avatar: Optional[bytes] = None):
        if user not in self.profile:
            return
        self.profile[user]["bio"]    = bio
        self.profile[user]["tastes"] = tastes
        if password is not None:
            self.profile[user]["password"] = password
        if avatar is not None:
            self.profile[user]["avatar"] = avatar
        self._rebuild_taste_dsu()

    def remove_user(self, user: str):
        if user in self.adj:
            for f in self.adj[user]:
                self.adj[f].discard(user)
            del self.adj[user]
        self.profile.pop(user, None)
        self.pending_requests.pop(user, None)
        self._rebuild_taste_dsu()

    #Friendships
    def add_friendship(self, u: str, v: str):
        if u == v:
            return
        for x in (u, v):
            if x not in self.adj:
                self.add_user(x, "", [], password="", avatar=None)
        self.adj[u].add(v)
        self.adj[v].add(u)

    def remove_friendship(self, u: str, v: str):
        self.adj.get(u, set()).discard(v)
        self.adj.get(v, set()).discard(u)

    #Friend Requests
    def send_friend_request(self, sender: str, receiver: str):
        if receiver not in self.profile:
            return
        if sender in self.adj.get(receiver, set()):
            return
        if sender in self.pending_requests.setdefault(receiver, set()):
            return
        self.pending_requests[receiver].add(sender)

    def get_incoming_requests(self, user: str) -> List[str]:
        return sorted(self.pending_requests.get(user, set()))

    def accept_friend_request(self, sender: str, receiver: str):
        if sender in self.pending_requests.get(receiver, set()):
            self.pending_requests[receiver].remove(sender)
            self.add_friendship(sender, receiver)

    def reject_friend_request(self, sender: str, receiver: str):
        self.pending_requests.get(receiver, set()).discard(sender)

    #Shortest Path (safe)
    def bfs_shortest_path(self, src: str, dst: str) -> Optional[List[str]]:
        if src not in self.adj or dst not in self.adj:
            return None
        if src == dst:
            return [src]
        from collections import deque
        q = deque([src])
        parent = {src: None}
        while q:
            n = q.popleft()
            for nei in self.adj.get(n, set()):
                if nei not in parent:
                    parent[nei] = n
                    if nei == dst:
                        path, cur = [], dst
                        while cur is not None:
                            path.append(cur)
                            cur = parent[cur]
                        return path[::-1]
                    q.append(nei)
        return None

    def mutual_friends(self, u: str, v: str) -> Set[str]:
        return self.adj.get(u, set()) & self.adj.get(v, set())

    #Recommendations (safe lookups)
    def recommend_friends(self, u: str) -> List[tuple]:
        if u not in self.adj:
            return []
        direct = self.adj[u]
        ut     = set(self.profile.get(u, {}).get("tastes", []))

        # FoF
        fof = set()
        for f in direct:
            fof |= self.adj.get(f, set())
        fof.discard(u)
        fof -= direct

        cu = self.users_in_same_taste_cluster(u)
        sc = {}
        for other in cu | fof:
            if other == u:
                continue
            ot = set(self.profile.get(other, {}).get("tastes", []))
            sc[other] = len(ut & ot)

        both         = sorted(cu & fof,          key=lambda x: (-sc[x], x))
        cluster_only = sorted(cu - set(both) - direct, key=lambda x: (-sc[x], x))
        fof_only     = sorted(fof - set(both),    key=lambda x: (-sc[x], x))

        return (
            [(n, 2, sc[n]) for n in both] +
            [(n, 1, sc[n]) for n in cluster_only] +
            [(n, 0, sc[n]) for n in fof_only]
        )

    def adjacency_list(self) -> Dict[str, List[str]]:
        return {u: sorted(v) for u, v in self.adj.items()}

    def connected_components(self) -> List[Set[str]]:
        visited, comps = set(), []
        def dfs(nd, comp):
            visited.add(nd)
            comp.add(nd)
            for nei in self.adj.get(nd, set()):
                if nei not in visited:
                    dfs(nei, comp)

        for nd in self.adj:
            if nd not in visited:
                comp = set()
                dfs(nd, comp)
                comps.append(comp)
        return comps

    def get_profile(self, u: str) -> Dict:
        return self.profile.get(u, {
            "bio": "",
            "tastes": [],
            "password": "",
            "avatar": None
        })

#DB
def load_graph_from_db() -> Graph:
    g = Graph()
    # load profiles
    for doc in profiles_col.find():
        g.add_user(
            doc["username"],
            doc.get("bio", ""),
            doc.get("tastes", []),
            password=doc.get("password", ""),
            avatar=doc.get("avatar", None)
        )
    #load friendships
    for doc in friends_col.find():
        g.adj[doc["username"]] = set(doc.get("friends", []))
    #load pending requests
    for doc in requests_col.find():
        g.pending_requests[doc["username"]] = set(doc.get("requests", []))
    g._rebuild_taste_dsu()
    return g

def save_user(user: str,
              bio: str,
              tastes: list,
              password: str = "",
              avatar: Optional[bytes] = None):
    fields = {"bio": bio, "tastes": tastes, "password": password}
    if avatar is not None:
        fields["avatar"] = avatar
    profiles_col.update_one(
        {"username": user},
        {"$set": fields},
        upsert=True
    )

def save_friends(user: str, friends: list):
    friends_col.update_one(
        {"username": user},
        {"$set": {"friends": friends}},
        upsert=True
    )

def save_requests(user: str, requests: list):
    requests_col.update_one(
        {"username": user},
        {"$set": {"requests": requests}},
        upsert=True
    )

def persist_graph(g: Graph):
    for u, p in g.profile.items():
        save_user(
            u,
            p.get("bio", ""),
            p.get("tastes", []),
            p.get("password", ""),
            avatar=p.get("avatar", None)
        )
    for u, fr in g.adj.items():
        save_friends(u, list(fr))
    for u, reqs in g.pending_requests.items():
        save_requests(u, list(reqs))
