from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple
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
            r = requests.request(method, url, timeout=30, **kwargs)
        except requests.RequestException as e:
            raise APIError(0, f"Network error calling {url}: {e}") from e

        if r.status_code >= 400:
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

    def create_hackathon(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._req("POST", "/hackathons", json=payload)

    def delete_hackathon(self, hackathon_id: str) -> None:
        self._req("DELETE", f"/hackathons/{hackathon_id}")

    def get_hackathon(self, hackathon_id: str) -> Dict[str, Any]:
        return self._req("GET", f"/hackathons/{hackathon_id}")

    # -------------------------
    # Teams
    # -------------------------
    def list_teams_by_hackathon(self, hackathon_id: str) -> List[Dict[str, Any]]:
        return self._req("GET", f"/teams/hackathon/{hackathon_id}") or []

    def create_team(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._req("POST", "/teams", json=payload)

    def delete_team(self, team_id: str) -> None:
        self._req("DELETE", f"/teams/{team_id}")

    def get_team(self, team_id: str) -> Dict[str, Any]:
        return self._req("GET", f"/teams/{team_id}")

    # membership (recommended REST)
    def add_participant_to_team(self, team_id: str, participant_id: str) -> None:
        self._req("POST", f"/teams/{team_id}/participants", json={"participant_id": participant_id})

    def remove_participant_from_team(self, team_id: str, participant_id: str) -> None:
        self._req("DELETE", f"/teams/{team_id}/participants/{participant_id}")

    # -------------------------
    # Participants
    # -------------------------
    def list_participants(self) -> List[Dict[str, Any]]:
        return self._req("GET", "/participants") or []

    def create_participant(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._req("POST", "/participants", json=payload)

    def delete_participant(self, participant_id: str) -> None:
        self._req("DELETE", f"/participants/{participant_id}")

    def get_participant(self, participant_id: str) -> Dict[str, Any]:
        return self._req("GET", f"/participants/{participant_id}")

    def find_participant_by_email(self, email: str) -> Dict[str, Any]:
        # if your backend supports it: GET /participants/by-email/{email}
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
        # adapt to your API shape:
        # Option A: /questions?category=a&category=b
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


def section_title(txt: str) -> None:
    st.markdown(f"### {txt}")


def show_error(e: Exception) -> None:
    st.error(str(e))


def to_iso_date(d: Optional[date]) -> Optional[str]:
    return d.isoformat() if d else None


def cached_choices_from_rows(rows: List[Dict[str, Any]], label_keys: List[str]) -> List[Tuple[str, str]]:
    """
    Returns list of (id, label) for selectbox.
    Expects rows have 'id'.
    """
    out: List[Tuple[str, str]] = []
    for r in rows:
        rid = str(r.get("id", ""))
        label_parts = [str(r.get(k, "")).strip() for k in label_keys]
        label = " • ".join([p for p in label_parts if p]) or rid
        out.append((rid, f"{label} — {rid}"))
    return out


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
    st.caption("Tip: if FastAPI runs in Docker, use --host 0.0.0.0 and expose port 8000.")


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
        with st.form("create_hackathon_form", clear_on_submit=False):
            name = st.text_input("Name", key="hk_name")

            use_dates = st.checkbox("Set dates", value=False)
            start_d = st.date_input("Start date", value=date.today(), disabled=not use_dates)
            end_d = st.date_input("End date", value=date.today(), disabled=not use_dates)

            submitted = st.form_submit_button("Create", type="primary")
            if submitted:
                try:
                    payload: Dict[str, Any] = {"name": name}
                    if use_dates:
                        payload["start_date"] = to_iso_date(start_d)
                        payload["end_date"] = to_iso_date(end_d)
                    else:
                        payload["start_date"] = None
                        payload["end_date"] = None

                    created = api.create_hackathon(payload)
                    st.success(f"Created hackathon: {created.get('id')} ({created.get('name')})")
                    st.rerun()
                except Exception as e:
                    show_error(e)

        section_title("Delete hackathon")
        with st.form("delete_hackathon_form"):
            hackathon_id = st.text_input("Hackathon ID", key="hk_del")
            del_submit = st.form_submit_button("Delete", type="secondary")
            if del_submit:
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
    colA, colB = st.columns([1.2, 1])

    with colA:
        section_title("Teams by hackathon")
        try:
            hackathons = api.list_hackathons()
            hackathon_choices = cached_choices_from_rows(hackathons, ["name"])
        except Exception as e:
            show_error(e)
            hackathon_choices = []

        selected_hid = ""
        if hackathon_choices:
            selected_hid = st.selectbox(
                "Hackathon",
                options=[c[0] for c in hackathon_choices],
                format_func=lambda x: dict(hackathon_choices).get(x, x),
                key="teams_hid_select",
            )
        else:
            selected_hid = st.text_input("Hackathon ID", key="teams_hid_manual")

        if st.button("Load teams", type="primary", disabled=not bool(selected_hid)):
            try:
                teams = api.list_teams_by_hackathon(selected_hid)
                st.session_state["teams_cache"] = teams
            except Exception as e:
                show_error(e)

        teams_cache = st.session_state.get("teams_cache", [])
        if teams_cache:
            st.dataframe(teams_cache, use_container_width=True, hide_index=True)

    with colB:
        section_title("Create team")
        with st.form("create_team_form"):
            team_name = st.text_input("Team name", key="team_create_name")
            create_submit = st.form_submit_button("Create", type="primary")
            if create_submit:
                try:
                    created = api.create_team({"hackathon_id": selected_hid, "name": team_name})
                    st.success(f"Created team: {created.get('id')} ({created.get('name')})")
                    st.rerun()
                except Exception as e:
                    show_error(e)

        section_title("Delete team")
        with st.form("delete_team_form"):
            team_id_del = st.text_input("Team ID", key="team_del")
            del_submit = st.form_submit_button("Delete", type="secondary")
            if del_submit:
                try:
                    api.delete_team(team_id_del)
                    st.success("Deleted")
                    st.rerun()
                except Exception as e:
                    show_error(e)

    st.divider()
    section_title("Team membership")

    col1, col2, col3 = st.columns([1.1, 1, 1])

    with col1:
        st.markdown("**Pick a team**")
        # use cached teams if available, else manual
        teams_for_choice = st.session_state.get("teams_cache", [])
        team_choices = cached_choices_from_rows(teams_for_choice, ["name"]) if teams_for_choice else []
        team_id = ""
        if team_choices:
            team_id = st.selectbox(
                "Team",
                options=[c[0] for c in team_choices],
                format_func=lambda x: dict(team_choices).get(x, x),
                key="team_pick",
            )
        else:
            team_id = st.text_input("Team ID", key="team_members_team_id")

        if st.button("Load team details", disabled=not bool(team_id)):
            try:
                team = api.get_team(team_id)
                st.json(team)
            except Exception as e:
                show_error(e)

    with col2:
        st.markdown("**Add participant to team**")
        try:
            participants = api.list_participants()
            participant_choices = cached_choices_from_rows(participants, ["email", "first_name", "last_name"])
        except Exception as e:
            show_error(e)
            participant_choices = []

        with st.form("add_participant_to_team_form"):
            add_team_id = team_id or st.text_input("Team ID (add)", key="add_team_id")
            pid = ""
            if participant_choices:
                pid = st.selectbox(
                    "Participant",
                    options=[c[0] for c in participant_choices],
                    format_func=lambda x: dict(participant_choices).get(x, x),
                    key="add_pid_select",
                )
            else:
                pid = st.text_input("Participant ID", key="add_pid_manual")

            add_submit = st.form_submit_button("Add", type="primary")
            if add_submit:
                try:
                    api.add_participant_to_team(add_team_id, pid)
                    st.success("Linked participant to team")
                    st.rerun()
                except Exception as e:
                    show_error(e)

    with col3:
        st.markdown("**Remove participant from team**")
        with st.form("remove_participant_from_team_form"):
            rm_team_id = team_id or st.text_input("Team ID (remove)", key="rm_team_id")
            rm_pid = st.text_input("Participant ID", key="rm_pid")
            rm_submit = st.form_submit_button("Remove", type="secondary")
            if rm_submit:
                try:
                    api.remove_participant_from_team(rm_team_id, rm_pid)
                    st.success("Removed link")
                    st.rerun()
                except Exception as e:
                    show_error(e)


# -------------------------
# Participants
# -------------------------
elif page == "Participants":
    colA, colB = st.columns([1.2, 1])

    with colA:
        section_title("Participants list")
        if st.button("Refresh", type="primary"):
            try:
                st.session_state["participants_cache"] = api.list_participants()
            except Exception as e:
                show_error(e)

        ps = st.session_state.get("participants_cache")
        if ps is None:
            try:
                ps = api.list_participants()
                st.session_state["participants_cache"] = ps
            except Exception as e:
                show_error(e)
                ps = []

        if ps:
            st.dataframe(ps, use_container_width=True, hide_index=True)

        section_title("Find by email")
        with st.form("find_participant_form"):
            email = st.text_input("Email", key="p_email_search")
            submitted = st.form_submit_button("Search")
            if submitted:
                try:
                    p = api.find_participant_by_email(email)
                    st.json(p)
                except Exception as e:
                    show_error(e)

    with colB:
        section_title("Create participant")
        with st.form("create_participant_form", clear_on_submit=False):
            fn = st.text_input("First name", key="p_fn")
            ln = st.text_input("Last name", key="p_ln")
            em = st.text_input("Email", key="p_em")
            submitted = st.form_submit_button("Create", type="primary")
            if submitted:
                try:
                    created = api.create_participant({"first_name": fn, "last_name": ln, "email": em})
                    st.success(f"Created participant: {created.get('id')}")
                    st.rerun()
                except Exception as e:
                    show_error(e)

        section_title("Delete participant")
        with st.form("delete_participant_form"):
            pid = st.text_input("Participant ID", key="p_del_id")
            submitted = st.form_submit_button("Delete", type="secondary")
            if submitted:
                try:
                    api.delete_participant(pid)
                    st.success("Deleted")
                    st.rerun()
                except Exception as e:
                    show_error(e)


# -------------------------
# Data Contexts
# -------------------------
elif page == "Data Contexts":
    cols = st.columns([1.2, 1])
    with cols[0]:
        section_title("Contexts list")
        if st.button("Refresh", type="primary"):
            try:
                ctxs = api.list_contexts()
                st.dataframe(ctxs, use_container_width=True, hide_index=True)
            except Exception as e:
                show_error(e)

    with cols[1]:
        section_title("Create context")
        with st.form("create_context_form"):
            name = st.text_input("Name", key="ctx_name")
            storage_link = st.text_input("Storage link", key="ctx_storage")
            is_active = st.checkbox("Active", value=True, key="ctx_active")
            schema_json = st.text_area("Schema definition (JSON)", value="{}", key="ctx_schema")

            submitted = st.form_submit_button("Create", type="primary")
            if submitted:
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
                    st.rerun()
                except Exception as e:
                    show_error(e)

        section_title("Delete context")
        with st.form("delete_context_form"):
            ctx_id = st.text_input("Context ID", key="ctx_del")
            submitted = st.form_submit_button("Delete", type="secondary")
            if submitted:
                try:
                    api.delete_context(ctx_id)
                    st.success("Deleted")
                    st.rerun()
                except Exception as e:
                    show_error(e)


# -------------------------
# Questions
# -------------------------
elif page == "Questions":
    cols = st.columns([1.2, 1])

    with cols[0]:
        section_title("Get questions by categories")
        with st.form("load_questions_form"):
            cats_raw = st.text_input("Categories (comma separated)", value="sql,python", key="q_cats")
            submitted = st.form_submit_button("Load", type="primary")
            if submitted:
                try:
                    cats = [c.strip() for c in cats_raw.split(",") if c.strip()]
                    qs = api.get_tasks_by_categories(cats)
                    st.session_state["questions_cache"] = qs
                except Exception as e:
                    show_error(e)

        qs = st.session_state.get("questions_cache", [])
        if qs:
            st.dataframe(qs, use_container_width=True, hide_index=True)

    with cols[1]:
        section_title("Get question by ID")
        with st.form("fetch_question_form"):
            qid = st.text_input("Question ID", key="q_id")
            submitted = st.form_submit_button("Fetch", type="primary")
            if submitted:
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
    with st.form("load_history_form"):
        team_id = st.text_input("Team ID", key="hist_team_id")
        submitted = st.form_submit_button("Load history", type="primary")
        if submitted:
            try:
                hist = api.get_team_history(team_id)
                st.dataframe(hist, use_container_width=True, hide_index=True)
            except Exception as e:
                show_error(e)
