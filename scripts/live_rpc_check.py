#!/usr/bin/env python3
"""Live RPC check against the V2 STAGING Supabase project (never production).

Reads SUPABASE_URL and SUPABASE_ANON_KEY from the environment. Never prints
keys, passwords, or JWTs. At most one signup per run.

Usage:
  SUPABASE_URL=... SUPABASE_ANON_KEY=... python3 supabase/staging/live_rpc_check.py
"""
from __future__ import annotations

import json
import os
import secrets
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

PROD_REF = "zdctckubirrlukbbrlwx"


def fail(msg: str, code: int = 1) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(code)


def env_url_key() -> tuple[str, str]:
    url = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
    key = os.environ.get("SUPABASE_ANON_KEY") or ""
    if not url or not key:
        fail("SUPABASE_URL and SUPABASE_ANON_KEY must be set")
    if PROD_REF in url:
        fail("refusing to run against the production project")
    if not url.startswith("https://") or not url.endswith(".supabase.co"):
        fail("SUPABASE_URL does not look like a Supabase https origin")
    return url, key


def request(method: str, url: str, headers: dict, body: dict | None = None, timeout: int = 30) -> tuple[int, dict | list | str]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            parsed: dict | list | str
            try:
                parsed = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                parsed = raw
            return resp.status, parsed
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = raw
        return exc.code, parsed


def headers(anon: str, jwt: str | None = None, prefer: str | None = None) -> dict:
    token = jwt or anon
    h = {
        "apikey": anon,
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if prefer:
        h["Prefer"] = prefer
    return h


def summarize_auth_payload(payload: dict) -> dict:
    user = payload.get("user") if isinstance(payload, dict) else None
    user = user if isinstance(user, dict) else {}
    session_keys = [k for k in ("access_token", "refresh_token", "token_type") if payload.get(k)]
    return {
        "has_access_token": bool(payload.get("access_token")),
        "session_fields_present": session_keys,
        "user_id_present": bool(user.get("id")),
        "email": user.get("email"),
        "email_confirmed_at": user.get("email_confirmed_at"),
        "confirmation_sent_at": user.get("confirmation_sent_at"),
        "aud": user.get("aud"),
        "role": user.get("role"),
        "error": payload.get("error") or payload.get("error_description") or payload.get("msg") or payload.get("message"),
        "error_code": payload.get("error_code") or payload.get("code"),
    }


def rpc(base: str, anon: str, jwt: str, name: str, args: dict) -> tuple[int, object]:
    return request("POST", f"{base}/rest/v1/rpc/{name}", headers(anon, jwt), args)


def select_user_topics(base: str, anon: str, jwt: str | None) -> tuple[int, object]:
    url = f"{base}/rest/v1/user_topics?select=id,user_id,topic_id,display_name,sort_order,active,removed_at&order=sort_order.asc"
    return request("GET", url, headers(anon, jwt))


def select_topics(base: str, anon: str, jwt: str | None) -> tuple[int, object]:
    url = f"{base}/rest/v1/topics?select=id,canonical_name&limit=5"
    return request("GET", url, headers(anon, jwt))


def main() -> None:
    base, anon = env_url_key()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    email = f"v2-live-{stamp}@test.invalid"
    password = secrets.token_urlsafe(24)
    results: list[str] = []

    def note(msg: str) -> None:
        print(msg)
        results.append(msg)

    note(f"target_host={base.split('//', 1)[1]}")
    note(f"signup_email={email}")
    note("signup_attempts=1")

    code, payload = request("POST", f"{base}/auth/v1/signup", headers(anon), {"email": email, "password": password})
    if not isinstance(payload, dict):
        fail(f"signup returned HTTP {code} with a non-JSON body")
    summary = summarize_auth_payload(payload)
    note(f"signup_http={code} auth_summary={json.dumps(summary, ensure_ascii=False)}")

    jwt = payload.get("access_token") if isinstance(payload.get("access_token"), str) else None
    confirmed = summary.get("email_confirmed_at")
    err_text = " ".join(str(summary.get(k) or "") for k in ("error", "error_code")).lower()

    if not jwt:
        if (not confirmed) or "confirm" in err_text or "email_not_confirmed" in err_text:
            print(
                "BLOCKED: signup did not return a session. This is the expected result when "
                "staging still has Confirm email / mailer_autoconfirm disabled for logins. "
                "Not retrying (signup emails are rate-limited). Turn confirm-email off, then "
                "rerun with a fresh v2-live-<ts>@test.invalid address.",
                file=sys.stderr,
            )
            sys.exit(2)
        fail(f"signup returned HTTP {code} without a session: {summary}")

    if not confirmed:
        note("WARN: session present but email_confirmed_at is empty; continuing with the JWT")

    # RLS: anon must not read user_topics; authenticated sees only own rows.
    anon_code, anon_body = select_user_topics(base, anon, None)
    note(f"rls_anon_user_topics http={anon_code} type={type(anon_body).__name__} ok_list={isinstance(anon_body, list)}")
    if anon_code == 200 and isinstance(anon_body, list) and len(anon_body) != 0:
        fail("anon was able to read user_topics rows; RLS/GRANT regression")

    topics_anon_code, _ = select_topics(base, anon, None)
    topics_auth_code, topics_auth_body = select_topics(base, anon, jwt)
    note(f"rls_topics anon_http={topics_anon_code} auth_http={topics_auth_code} auth_empty_or_denied={topics_auth_code != 200 or topics_auth_body == []}")

    created: list[dict] = []

    def request_topic(name: str) -> object:
        code, body = rpc(base, anon, jwt, "request_topic", {"p_name": name})
        note(f"request_topic name={name!r} http={code} body={body}")
        return body

    # Existing seed (should not consume the daily-new cap).
    cafe = request_topic("Café")
    # Three new topics — daily_new_per_user default is 3.
    for suffix in ("a", "b", "c"):
        request_topic(f"v2-live-{stamp}-{suffix}")
    # Fourth new topic should hit the daily cap, not the 5-active cap
    # (only 4 active so far: Café + 3 new).
    fourth = request_topic(f"v2-live-{stamp}-d")
    if isinstance(fourth, dict) and fourth.get("error") != "daily_cap" and fourth.get("status") != "daily_cap":
        note(f"WARN: expected daily_cap on 4th new topic, got {fourth}")

    mine_code, mine = select_user_topics(base, anon, jwt)
    if mine_code != 200 or not isinstance(mine, list):
        fail(f"authenticated SELECT user_topics failed: http={mine_code} body={mine}")
    user_ids = {row.get("user_id") for row in mine}
    note(f"rls_own_user_topics http={mine_code} count={len(mine)} distinct_user_ids={len(user_ids)} all_active={all(r.get('active') for r in mine)}")
    if len(user_ids) != 1:
        fail("user_topics rows were not limited to a single user_id")

    active = [row for row in mine if row.get("active")]
    if not active:
        fail("no active user_topics after request_topic calls")
    first = active[0]
    utid = first["id"]

    code, body = rpc(base, anon, jwt, "rename_user_topic", {"p_user_topic_id": utid, "p_display_name": "直播改名"})
    note(f"rename_user_topic http={code} body={body}")
    code, body = rpc(base, anon, jwt, "move_user_topic", {"p_user_topic_id": utid, "p_sort_order": 10})
    note(f"move_user_topic http={code} body={body}")

    # Cap of 5: cannot fully exercise with only 1 existing + 3 new today.
    # Document remaining headroom and the daily-cap result above.
    note(f"active_count_after_setup={len(active)} (max_active=5; daily_new_per_user=3)")

    # Cleanup: soft-remove every topic this user created/attached.
    _, mine = select_user_topics(base, anon, jwt)
    cleaned = 0
    if isinstance(mine, list):
        for row in mine:
            if not row.get("active"):
                continue
            code, body = rpc(base, anon, jwt, "remove_user_topic", {"p_user_topic_id": row["id"]})
            note(f"remove_user_topic id=…{str(row['id'])[-8:]} http={code} body={body}")
            if isinstance(body, dict) and body.get("status") == "ok":
                cleaned += 1
    _, left = select_user_topics(base, anon, jwt)
    left_active = [r for r in left if isinstance(r, dict) and r.get("active")] if isinstance(left, list) else "error"
    note(f"cleanup removed={cleaned} remaining_active={left_active if isinstance(left_active, int) or left_active == 'error' else len(left_active)}")
    if left_active not in ("error",) and len(left_active) != 0:
        fail("cleanup left active user_topics rows")
    note("PASS: live RPC check finished")


if __name__ == "__main__":
    main()
