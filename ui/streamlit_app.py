from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

import requests
import streamlit as st


# -------------------------
# Config
# -------------------------
DEFAULT_API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")


@dataclass(frozen=True)
class APIError(Exception):
    status_code: int
    detail: str

    def __str__(self) -> str:
        return f"[{self.status_code}] {self.detail}"


class API:
    def __init__(self, base_url: str):
        self.base = base_url.rstrip("/")

    def _req(self, method: str, path: str, **kwargs) -> Any:
        url = f"{self.base}{path}"
        try:
            r = requests.request(method, url, timeout=20, **kwargs)
        except requests.RequestException as e:
            raise APIError(0, f"Network error calling {url}: {e}") from e

        if r.status_code >= 400:
            detail = None
            try:
                detail = r.json()
            except Exception:
                detail = r.text
            raise APIError(r.status_code, str(detail))

        if r.status_code == 204:
            return None
        if not r.content:
            return None
        return r.json()

    # -------------------------
    # Hackathons
    # -------------------------
    def list_hackathons(self) -> List[Dict[str, Any]]:
        return self._req("GET", "/hackathons") or []

    def create_hackathon(self, name: str, start_date: Optional[str], end_date: Optional[str]) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"name": name, "start_date": start_date, "end_date": end_date}
        return self._req("POST", "/hackathons", json=payload)

    def delete_hackathon(self, hackathon_id: str) -> None:
        self._req("DELETE", f"/hackathons/{hackathon_id}")

    def get_hackathon(self, hackathon_id: str) -> Dict[str, Any]:
        return self._req("GET", f"/hackathons/{hackathon_id}")

    # -------------------------
    # Teams
    # -------------------------
    def list_teams_by_hackathon(self, hackathon_id: str) -> List[Dict[str, Any]]:
        return self._req("GET", f"/hackathons/{hackathon_id}/teams") or []

    def create_team(self, hackathon_id: str, name: str) -> Dict[str, Any]:
        return self._req("POST", f"/hackathons/{hackathon_id}/teams", json={"name": name})

    def delete_team(self, team_id: str) -> None:
        self._req("DELETE", f"/teams/{team_id}")

    def get_team(self, team_id: str) -> Dict[str, Any]:
        return self._req("GET", f"/teams/{team_id}")

    def add_participant_to_team(self, team_id: str, participant: Dict[str, Any]) -> None:
        self._req("POST", f"/teams/{team_id}/participants", json=participant)

    def remove_participant_from_team(self, team_id: str, participant_id: str) -> None:
        self._req("DELETE", f"/teams/{team_id}/participants/{participant_id}")

    # -------------------------
    # Participants
    # -------------------------
    def list_participants(self) -> List[Dict[str, Any]]:
        return self._req("GET", "/participants") or []

    def create_participant(self, first_name: str, last_name: str, email: str) -> Dict[str, Any]:
        return self._req("POST", "/participants", json={"first_name": first_name, "last_name": last_name, "email": email})

    def delete_participant(self, participant_id: str) -> None:
        self._req("DELETE", f"/participants/{participant_id}")

    def get_participant(self, participant_id: str) -> Dict[str, Any]:
        return self._req("GET", f"/participants/{participant_id}")

    def find_participant_by_email(self, email: str) -> Dict[str, Any]:
        return self._req("GET", f"/participants/by-email/{email}")

    # -------------------------
    # Data Contexts
    # -------------------------
    def list_contexts(self) -> List[Dict[str, Any]]:
        return self._req("GET", "/contexts") or []

    def create_context(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._req("POST", "/contexts", json=payload)

    def delete_context(self, context_id: str) -> None:
        self._req("DELETE", f"/contexts/{context_id}")

    # -------------------------
    # Questions
    # -------------------------
    def get_tasks_by_categories(self, categories: List[str]) -> List[Dict[str, Any]]:
        # expects ?categories=a&categories=b or POST body depending on your API
        # Here: GET /questions?category=...
        params = [("category", c) for c in categories]
        return self._req("GET", "/questions", params=params) or []

    def get_task_by_id(self, question_id: str) -> Dict[str, Any]:
        return self._req("GET", f"/questions/{question_id}")

    # -------------------------
    # Analytics
    # -------------------------
    def get_leaderboard(self) -> List[Dict[str, Any]]:
        return self._req("GET", "/leaderboard") or []

    def get_team_history(self, team_id: str) -> List[Dict[str, Any]]:
        return self._req("GET", f"/teams/{team_id}/history") or []


# -------------------------
# UI helpers
# -------------------------
def iso_or_none(d: Optional[datetime]) -> Optional[str]:
    if d is None:
        return None
    return d.isoformat()


def section_title(txt: str) -> None:
    st.markdown(f"### {txt}")


def show_error(e: Exception) -> None:
    st.error(str(e))


# -------------------------
# Streamlit App
# -------------------------
st.set_page_config(page_title="Benchmarker Admin", layout="wide")

st.title("Benchmarker Admin (Streamlit)")
st.caption("Admin UI on top of your FastAPI benchmarker backend")

with st.sidebar:
    st.subheader("Connection")
    api_base = st.text_input("API base URL", value=DEFAULT_API_BASE)
    api = API(api_base)

    st.divider()
    page = st.radio(
        "Navigate",
        [
            "Hackathons",
            "Teams",
            "Participants",
            "Data Contexts",
            "Questions",
            "Leaderboard",
            "Team History",
        ],
        index=0,
    )

    st.divider()
    st.caption("Tip: if you run FastAPI in Docker, ensure it binds 0.0.0.0 and expose port 8000.")

# -------------------------
# Hackathons
# -------------------------
if page == "Hackathons":
    colA, colB = st.columns([1.2, 1])

    with colA:
        section_title("Hackathons list")
        try:
            hs = api.list_hackathons()
            st.dataframe(hs, use_container_width=True, hide_index=True)
        except Exception as e:
            show_error(e)
            hs = []

    with colB:
        section_title("Create hackathon")
        name = st.text_input("Name", key="hk_name")
        start = st.date_input("Start date (optional)", value=None, key="hk_start")
        end = st.date_input("End date (optional)", value=None, key="hk_end")

        # Streamlit date_input can't be None unless configured; handle gracefully:
        start_iso = start.isoformat() if start else None
        end_iso = end.isoformat() if end else None

        if st.button("Create", type="primary"):
            try:
                created = api.create_hackathon(name=name, start_date=start_iso, end_date=end_iso)
                st.success(f"Created hackathon: {created.get('id')} ({created.get('name')})")
                st.rerun()
            except Exception as e:
                show_error(e)

        section_title("Delete hackathon")
        hackathon_id = st.text_input("Hackathon ID to delete", key="hk_del")
        if st.button("Delete", type="secondary"):
            try:
                api.delete_hackathon(hackathon_id)
                st.success("Deleted")
                st.rerun()
            except Exception as e:
                show_error(e)

# -------------------------
# Teams
# -------------------------
elif page == "Teams":
    section_title("Teams by hackathon")
    hackathon_id = st.text_input("Hackathon ID", key="teams_hid")

    cols = st.columns([1.2, 1])
    with cols[0]:
        if st.button("Load teams"):
            st.session_state["teams_loaded"] = True

        if st.session_state.get("teams_loaded") and hackathon_id:
            try:
                teams = api.list_teams_by_hackathon(hackathon_id)
                st.dataframe(teams, use_container_width=True, hide_index=True)
            except Exception as e:
                show_error(e)

    with cols[1]:
        section_title("Create team")
        team_name = st.text_input("Team name", key="team_create_name")
        if st.button("Create team", type="primary"):
            try:
                created = api.create_team(hackathon_id, team_name)
                st.success(f"Created team: {created.get('id')} ({created.get('name')})")
            except Exception as e:
                show_error(e)

        section_title("Delete team")
        team_id_del = st.text_input("Team ID to delete", key="team_del")
        if st.button("Delete team", type="secondary"):
            try:
                api.delete_team(team_id_del)
                st.success("Deleted")
            except Exception as e:
                show_error(e)

    st.divider()
    section_title("Team membership")
    c1, c2 = st.columns(2)

    with c1:
        team_id = st.text_input("Team ID", key="team_members_team_id")
        if st.button("Load team details"):
            try:
                team = api.get_team(team_id)
                st.json(team)
            except Exception as e:
                show_error(e)

    with c2:
        st.markdown("**Add participant to team**")
        add_team_id = st.text_input("Team ID (add)", key="add_team_id")
        fn = st.text_input("First name", key="add_fn")
        ln = st.text_input("Last name", key="add_ln")
        email = st.text_input("Email", key="add_email")
        if st.button("Add participant"):
            try:
                api.add_participant_to_team(add_team_id, {"first_name": fn, "last_name": ln, "email": email})
                st.success("Added (or upserted) participant and linked to team")
            except Exception as e:
                show_error(e)

        st.markdown("**Remove participant from team**")
        rm_team_id = st.text_input("Team ID (remove)", key="rm_team_id")
        rm_pid = st.text_input("Participant ID", key="rm_pid")
        if st.button("Remove participant"):
            try:
                api.remove_participant_from_team(rm_team_id, rm_pid)
                st.success("Removed link")
            except Exception as e:
                show_error(e)

# -------------------------
# Participants
# -------------------------
elif page == "Participants":
    cols = st.columns([1.2, 1])
    with cols[0]:
        section_title("Participants list")
        if st.button("Load participants", type="primary"):
            try:
                ps = api.list_participants()
                st.dataframe(ps, use_container_width=True, hide_index=True)
            except Exception as e:
                show_error(e)

        section_title("Find by email")
        email = st.text_input("Email to search", key="p_email_search")
        if st.button("Search"):
            try:
                p = api.find_participant_by_email(email)
                st.json(p)
            except Exception as e:
                show_error(e)

    with cols[1]:
        section_title("Create participant")
        fn = st.text_input("First name", key="p_fn")
        ln = st.text_input("Last name", key="p_ln")
        em = st.text_input("Email", key="p_em")
        if st.button("Create", type="primary"):
            try:
                created = api.create_participant(fn, ln, em)
                st.success(f"Created participant: {created.get('id')}")
            except Exception as e:
                show_error(e)

        section_title("Delete participant")
        pid = st.text_input("Participant ID to delete", key="p_del_id")
        if st.button("Delete", type="secondary"):
            try:
                api.delete_participant(pid)
                st.success("Deleted")
            except Exception as e:
                show_error(e)

# -------------------------
# Data Contexts
# -------------------------
elif page == "Data Contexts":
    cols = st.columns([1.2, 1])
    with cols[0]:
        section_title("Contexts list")
        if st.button("Load contexts", type="primary"):
            try:
                ctxs = api.list_contexts()
                st.dataframe(ctxs, use_container_width=True, hide_index=True)
            except Exception as e:
                show_error(e)

    with cols[1]:
        section_title("Create context")
        name = st.text_input("Name", key="ctx_name")
        storage_link = st.text_input("Storage link", key="ctx_storage")
        is_active = st.checkbox("Active", value=True, key="ctx_active")
        schema_json = st.text_area("Schema definition (JSON)", value="{}", key="ctx_schema")

        if st.button("Create context", type="primary"):
            try:
                import json
                payload = {
                    "name": name,
                    "storage_link": storage_link,
                    "is_active": is_active,
                    "schema_definition": json.loads(schema_json or "{}"),
                }
                created = api.create_context(payload)
                st.success(f"Created context: {created.get('id')}")
            except Exception as e:
                show_error(e)

        section_title("Delete context")
        ctx_id = st.text_input("Context ID to delete", key="ctx_del")
        if st.button("Delete context", type="secondary"):
            try:
                api.delete_context(ctx_id)
                st.success("Deleted")
            except Exception as e:
                show_error(e)

# -------------------------
# Questions
# -------------------------
elif page == "Questions":
    cols = st.columns([1.2, 1])

    with cols[0]:
        section_title("Get questions by categories")
        cats_raw = st.text_input("Categories (comma separated)", value="sql,python", key="q_cats")
        if st.button("Load questions", type="primary"):
            try:
                cats = [c.strip() for c in cats_raw.split(",") if c.strip()]
                qs = api.get_tasks_by_categories(cats)
                st.dataframe(qs, use_container_width=True, hide_index=True)
            except Exception as e:
                show_error(e)

    with cols[1]:
        section_title("Get question by ID")
        qid = st.text_input("Question ID", key="q_id")
        if st.button("Fetch", type="primary"):
            try:
                q = api.get_task_by_id(qid)
                st.json(q)
            except Exception as e:
                show_error(e)

# -------------------------
# Leaderboard
# -------------------------
elif page == "Leaderboard":
    section_title("Leaderboard")
    if st.button("Refresh leaderboard", type="primary"):
        try:
            lb = api.get_leaderboard()
            st.dataframe(lb, use_container_width=True, hide_index=True)
        except Exception as e:
            show_error(e)

# -------------------------
# Team History
# -------------------------
elif page == "Team History":
    section_title("Team evaluation history")
    team_id = st.text_input("Team ID", key="hist_team_id")
    if st.button("Load history", type="primary"):
        try:
            hist = api.get_team_history(team_id)
            st.dataframe(hist, use_container_width=True, hide_index=True)
        except Exception as e:
            show_error(e)
