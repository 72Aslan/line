import os
from functools import lru_cache


@lru_cache(maxsize=1)
def get_client():
    """
    延後建立 Supabase client（lazy），避免每一次 webhook 請求（包含不需要
    資料庫的路徑）都在 import 階段就付出建立 client 的成本。
    用 SUPABASE_SERVICE_ROLE_KEY 存取，走 REST API，適合 serverless（不會佔用資料庫連線池）。
    """
    from supabase import create_client

    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY 環境變數未設定")
    return create_client(url, key)


# ------------------ users ------------------

def upsert_user(line_user_id, display_name=None, picture_url=None):
    client = get_client()
    payload = {"line_user_id": line_user_id}
    if display_name is not None:
        payload["display_name"] = display_name
    if picture_url is not None:
        payload["picture_url"] = picture_url
    client.table("users").upsert(payload, on_conflict="line_user_id").execute()


# ------------------ events ------------------

def create_draft_event(owner_line_user_id, match_data):
    """開團訊息經 AI 解析後，先以 draft 狀態寫入資料庫。"""
    client = get_client()
    upsert_user(owner_line_user_id)

    payload = {
        "owner_line_user_id": owner_line_user_id,
        "date_text": match_data.get("date"),
        "time_text": match_data.get("time"),
        "location": match_data.get("location"),
        "limit_players": match_data.get("limit_players") or 0,
        "fee": match_data.get("fee"),
        "level": match_data.get("level"),
        "shuttlecock": match_data.get("shuttlecock"),
        "status": "draft",
    }
    result = client.table("events").insert(payload).execute()
    return result.data[0]


def confirm_event(event_id):
    """團主按下「確認開團」後，把場次從 draft 轉為 open（正式公開報名）。"""
    client = get_client()
    result = (
        client.table("events")
        .update({"status": "open", "updated_at": "now()"})
        .eq("id", event_id)
        .execute()
    )
    if not result.data:
        return None
    return result.data[0]


def get_event(event_id):
    client = get_client()
    result = client.table("events").select("*").eq("id", event_id).limit(1).execute()
    return result.data[0] if result.data else None


def get_latest_open_event(owner_line_user_id=None):
    """
    MVP 簡化版查詢：先假設一次只會有一場「開放中」的場次可查。
    之後做到規格書第七章（多場次查詢）時，再擴充成依日期/關鍵字篩選。
    """
    client = get_client()
    query = client.table("events").select("*").in_("status", ["open", "full"])
    if owner_line_user_id:
        query = query.eq("owner_line_user_id", owner_line_user_id)
    result = query.order("created_at", desc=True).limit(1).execute()
    return result.data[0] if result.data else None


# ------------------ registrations ------------------

def _count_by_status(event_id, status):
    client = get_client()
    result = (
        client.table("registrations")
        .select("id", count="exact")
        .eq("event_id", event_id)
        .eq("status", status)
        .execute()
    )
    return result.count or 0


def count_registered(event_id):
    return _count_by_status(event_id, "registered")


def count_waitlisted(event_id):
    return _count_by_status(event_id, "waitlisted")


def get_active_registration(event_id, line_user_id):
    client = get_client()
    result = (
        client.table("registrations")
        .select("*")
        .eq("event_id", event_id)
        .eq("line_user_id", line_user_id)
        .neq("status", "cancelled")
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def create_registration(event_id, line_user_id):
    """
    寫入報名。回傳格式：
    {
        "already_registered": bool,
        "status": "registered" | "waitlisted",
        "position_number": int,
        "limit": int,
    }
    """
    event = get_event(event_id)
    if not event:
        raise ValueError("找不到這個場次，可能已經被刪除或取消")

    existing = get_active_registration(event_id, line_user_id)
    if existing:
        return {
            "already_registered": True,
            "status": existing["status"],
            "position_number": existing["position_number"],
            "limit": event["limit_players"],
        }

    upsert_user(line_user_id)

    limit = event.get("limit_players") or 0
    registered_count = count_registered(event_id)

    if registered_count < limit:
        status = "registered"
        position_number = registered_count + 1
    else:
        status = "waitlisted"
        position_number = count_waitlisted(event_id) + 1

    client = get_client()
    result = (
        client.table("registrations")
        .insert(
            {
                "event_id": event_id,
                "line_user_id": line_user_id,
                "status": status,
                "position_number": position_number,
            }
        )
        .execute()
    )
    row = result.data[0]

    # 若場次因此額滿，順手更新場次狀態
    if status == "registered" and registered_count + 1 >= limit:
        client.table("events").update({"status": "full", "updated_at": "now()"}).eq(
            "id", event_id
        ).execute()

    return {
        "already_registered": False,
        "status": row["status"],
        "position_number": row["position_number"],
        "limit": limit,
    }
