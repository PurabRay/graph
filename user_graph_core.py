
import streamlit as st
from typing import List, Set, Dict, Optional

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
        # Return all tastes in the same clusters as any in taste_list
        roots = {self.find(t) for t in taste_list}
        return {t for t in self.parent if self.find(t) in roots}

#Using Graph + Profile
class Graph:
    def __init__(self):
        self.adj: Dict[str, Set[str]] = {}
        self.profile: Dict[str, Dict] = {}  # {user: {bio, tastes, password}}
        self.taste_list = [
            "Rock Music", "Classical Music", "Hip-Hop", "Jazz",
            "Football", "Basketball", "Cricket", "Badminton",
            "Science Fiction", "Fantasy", "Mystery", "Romance",
            "Coding", "Gaming", "Cooking", "Travel"
        ]
        self.taste_dsu = DSU()

    #DSU logic
    def _rebuild_taste_dsu(self):
        self.taste_dsu = DSU()
        for taste in self.taste_list:
            self.taste_dsu.find(taste)
        for p in self.profile.values():
            tastes = p["tastes"]
            if len(tastes) > 1:
                for i in range(1, len(tastes)):
                    self.taste_dsu.union(tastes[0], tastes[i])

    def users_in_same_taste_cluster(self, user: str) -> Set[str]:
        """All users sharing any transitive taste cluster with user (excluding direct self)."""
        if user not in self.profile:
            return set()
        user_tastes = self.profile[user]["tastes"]
        if not user_tastes:
            return set()
        cluster_tastes = self.taste_dsu.cluster_members(user_tastes)
        users = set()
        for other, prof in self.profile.items():
            if other == user:
                continue
            if set(prof["tastes"]) & cluster_tastes:
                users.add(other)
        return users

    #CRUD
    def add_user(self, user: str, bio: str, tastes: List[str], password: str = ""):
        user = user.strip()
        if not user or user in self.adj:
            return
        self.adj[user] = set()
        self.profile[user] = {"bio": bio, "tastes": tastes, "password": password}
        self._rebuild_taste_dsu()

    def edit_profile(self, user: str, bio: str, tastes: List[str], password: str = None):
        if user not in self.profile:
            return
        self.profile[user]["bio"] = bio
        self.profile[user]["tastes"] = tastes
        if password is not None:
            self.profile[user]["password"] = password
        self._rebuild_taste_dsu()

    def remove_user(self, user: str):
        if user in self.adj:
            for friend in list(self.adj[user]):
                self.adj[friend].remove(user)
            del self.adj[user]
        if user in self.profile:
            del self.profile[user]
        self._rebuild_taste_dsu()

    def add_friendship(self, u: str, v: str):
        if u == v:
            return
        for name in (u, v):
            if name not in self.adj:
                self.add_user(name, "", [])
        self.adj[u].add(v)
        self.adj[v].add(u)

    def remove_friendship(self, u: str, v: str):
        if u in self.adj and v in self.adj[u]:
            self.adj[u].remove(v)
            self.adj[v].remove(u)

    #Graph Algorithms
    def bfs_shortest_path(self, src: str, dst: str) -> Optional[List[str]]:
        if src not in self.adj or dst not in self.adj:
            return None
        if src == dst:
            return [src]
        from collections import deque
        q = deque([src])
        parent = {src: None}
        while q:
            node = q.popleft()
            for nei in self.adj[node]:
                if nei not in parent:
                    parent[nei] = node
                    if nei == dst:
                        return self._reconstruct(parent, dst)
                    q.append(nei)
        return None

    def _reconstruct(self, parent, node):
        path = []
        while node is not None:
            path.append(node)
            node = parent[node]
        return path[::-1]

    def mutual_friends(self, u: str, v: str) -> Set[str]:
        if u not in self.adj or v not in self.adj:
            return set()
        return self.adj[u] & self.adj[v]

    def recommend_friends(self, u: str) -> List[tuple]:
        if u not in self.adj:
            return []
        direct = self.adj[u]
        user_tastes = set(self.profile[u]["tastes"])
        #Friends-of-friends
        fof = set()
        for f in direct:
            fof.update(self.adj[f])
        fof.discard(u)
        fof -= direct
        #Users in any shared taste cluster
        cluster_users = self.users_in_same_taste_cluster(u)
        shared_taste_counts = {}
        for other in cluster_users | fof:
            if other == u: continue
            shared = user_tastes & set(self.profile[other]["tastes"])
            shared_taste_counts[other] = len(shared)
        #Build buckets
        both = [name for name in (cluster_users & fof)]
        cluster_only = [name for name in (cluster_users - set(both) - direct)]
        fof_only = [name for name in (fof - set(both))]
        both = sorted(both, key=lambda x: (-shared_taste_counts.get(x,0), x))
        cluster_only = sorted(cluster_only, key=lambda x: (-shared_taste_counts.get(x,0), x))
        fof_only = sorted(fof_only, key=lambda x: (-shared_taste_counts.get(x,0), x))
        ranked = [(name, 2, shared_taste_counts.get(name,0)) for name in both] + \
                 [(name, 1, shared_taste_counts.get(name,0)) for name in cluster_only] + \
                 [(name, 0, shared_taste_counts.get(name,0)) for name in fof_only]
        return ranked

    def adjacency_list(self):
        return {u: sorted(list(v)) for u, v in self.adj.items()}

    def connected_components(self):
        visited = set()
        comps = []
        def dfs(n, comp):
            visited.add(n)
            comp.add(n)
            for nei in self.adj[n]:
                if nei not in visited:
                    dfs(nei, comp)
        for node in self.adj:
            if node not in visited:
                comp = set()
                dfs(node, comp)
                comps.append(comp)
        return comps

    def get_profile(self, user):
        return self.profile.get(user, {"bio": "", "tastes": [], "password": ""})

