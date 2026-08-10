import os
from functools import lru_cache
from datetime import datetime, timezone


# ==================================================
# Supabase Client
# ==================================================

@lru_cache(maxsize=1)
def get_client():

    from supabase import create_client

    url = os.environ.get(
        "SUPABASE_URL",
        "",
    )

    key = os.environ.get(
        "SUPABASE_SERVICE_ROLE_KEY",
        "",
    )

    if not url or not key:

        raise RuntimeError(
            "SUPABASE_URL / "
            "SUPABASE_SERVICE_ROLE_KEY "
            "環境變數未設定"
        )

    return create_client(
        url,
        key,
    )


# ==================================================
# Time
# ==================================================

def _now_iso():

    return datetime.now(
        timezone.utc
    ).isoformat()


# ==================================================
# Users
# ==================================================

def upsert_user(
    line_user_id,
    display_name=None,
    picture_url=None,
):

    client = get_client()

    payload = {
        "line_user_id": line_user_id,
    }

    if display_name is not None:

        payload[
            "display_name"
        ] = display_name

    if picture_url is not None:

        payload[
            "picture_url"
        ] = picture_url

    client.table(
        "users"
    ).upsert(
        payload,
        on_conflict="line_user_id",
    ).execute()


# ==================================================
# Events
# ==================================================

def create_draft_event(
    owner_line_user_id,
    match_data,
):
    """
    建立草稿活動。

    狀態：
        draft

    團主按確認後：
        draft -> open
    """

    client = get_client()

    # 確保 users 存在
    upsert_user(
        owner_line_user_id
    )

    payload = {
        "owner_line_user_id":
            owner_line_user_id,

        "date_text":
            match_data.get("date"),

        "time_text":
            match_data.get("time"),

        "location":
            match_data.get("location"),

        "limit_players":
            int(
                match_data.get(
                    "limit_players"
                ) or 0
            ),

        "fee":
            match_data.get("fee"),

        "level":
            match_data.get("level")
            or "不限",

        "shuttlecock":
            match_data.get(
                "shuttlecock"
            )
            or "未設定",

        "status":
            "draft",
    }

    print(
        "[DB] CREATE DRAFT:",
        payload,
    )

    result = (
        client
        .table("events")
        .insert(payload)
        .execute()
    )

    if not result.data:

        raise RuntimeError(
            "建立 draft event 失敗"
        )

    return result.data[0]


def confirm_event(
    event_id,
    owner_line_user_id,
):
    """
    只有原本建立活動的團主，
    才能將 draft -> open。

    同時限制：
        status 必須是 draft
    """

    client = get_client()

    result = (
        client
        .table("events")
        .update({
            "status": "open",
            "updated_at": _now_iso(),
        })
        .eq(
            "id",
            event_id,
        )
        .eq(
            "owner_line_user_id",
            owner_line_user_id,
        )
        .eq(
            "status",
            "draft",
        )
        .execute()
    )

    if not result.data:

        return None

    return result.data[0]


def get_event(
    event_id,
):

    client = get_client()

    result = (
        client
        .table("events")
        .select("*")
        .eq(
            "id",
            event_id,
        )
        .limit(1)
        .execute()
    )

    if result.data:

        return result.data[0]

    return None


def get_latest_open_event(
    owner_line_user_id=None,
):
    """
    MVP：
    取得最近一場 open / full 的球局。
    """

    client = get_client()

    query = (
        client
        .table("events")
        .select("*")
        .in_(
            "status",
            [
                "open",
                "full",
            ],
        )
    )

    if owner_line_user_id:

        query = query.eq(
            "owner_line_user_id",
            owner_line_user_id,
        )

    result = (
        query
        .order(
            "created_at",
            desc=True,
        )
        .limit(1)
        .execute()
    )

    if result.data:

        return result.data[0]

    return None


# ==================================================
# Registrations
# ==================================================

def _count_by_status(
    event_id,
    status,
):

    client = get_client()

    result = (
        client
        .table("registrations")
        .select(
            "id",
            count="exact",
        )
        .eq(
            "event_id",
            event_id,
        )
        .eq(
            "status",
            status,
        )
        .execute()
    )

    return result.count or 0


def count_registered(
    event_id,
):

    return _count_by_status(
        event_id,
        "registered",
    )


def count_waitlisted(
    event_id,
):

    return _count_by_status(
        event_id,
        "waitlisted",
    )


def get_active_registration(
    event_id,
    line_user_id,
):

    client = get_client()

    result = (
        client
        .table("registrations")
        .select("*")
        .eq(
            "event_id",
            event_id,
        )
        .eq(
            "line_user_id",
            line_user_id,
        )
        .neq(
            "status",
            "cancelled",
        )
        .limit(1)
        .execute()
    )

    if result.data:

        return result.data[0]

    return None


def create_registration(
    event_id,
    line_user_id,
):
    """
    建立報名。

    回傳：

    {
        "already_registered": bool,
        "status": "registered" | "waitlisted",
        "position_number": int,
        "limit": int
    }
    """

    # ----------------------------------------------
    # 取得活動
    # ----------------------------------------------

    event = get_event(
        event_id
    )

    if not event:

        raise ValueError(
            "找不到這個場次，"
            "可能已經被刪除。"
        )

    # ----------------------------------------------
    # 活動狀態
    # ----------------------------------------------

    event_status = event.get(
        "status"
    )

    if event_status not in [
        "open",
        "full",
    ]:

        if event_status == "draft":

            raise ValueError(
                "這場球局尚未正式開放報名。"
            )

        if event_status == "cancelled":

            raise ValueError(
                "這場球局已取消，"
                "目前無法報名。"
            )

        if event_status == "completed":

            raise ValueError(
                "這場球局已經結束。"
            )

        raise ValueError(
            "這場球局目前沒有開放報名。"
        )

    # ----------------------------------------------
    # 重複報名
    # ----------------------------------------------

    existing = (
        get_active_registration(
            event_id,
            line_user_id,
        )
    )

    if existing:

        return {
            "already_registered": True,
            "status": existing[
                "status"
            ],
            "position_number":
                existing[
                    "position_number"
                ],
            "limit":
                event[
                    "limit_players"
                ],
        }

    # ----------------------------------------------
    # User
    # ----------------------------------------------

    upsert_user(
        line_user_id
    )

    # ----------------------------------------------
    # 名額
    # ----------------------------------------------

    try:

        limit = int(
            event.get(
                "limit_players"
            ) or 0
        )

    except (
        ValueError,
        TypeError,
    ):

        limit = 0

    if limit <= 0:

        raise ValueError(
            "這場球局沒有設定有效名額。"
        )

    # ----------------------------------------------
    # 計算正取
    # ----------------------------------------------

    registered_count = (
        count_registered(
            event_id
        )
    )

    if registered_count < limit:

        status = "registered"

        position_number = (
            registered_count + 1
        )

    else:

        status = "waitlisted"

        position_number = (
            count_waitlisted(
                event_id
            ) + 1
        )

    # ----------------------------------------------
    # Insert
    # ----------------------------------------------

    client = get_client()

    result = (
        client
        .table("registrations")
        .insert({
            "event_id":
                event_id,

            "line_user_id":
                line_user_id,

            "status":
                status,

            "position_number":
                position_number,
        })
        .execute()
    )

    if not result.data:

        raise RuntimeError(
            "建立報名資料失敗"
        )

    row = result.data[0]

    # ----------------------------------------------
    # 正好額滿
    # ----------------------------------------------

    if (
        status == "registered"
        and registered_count + 1
        >= limit
    ):

        (
            client
            .table("events")
            .update({
                "status": "full",
                "updated_at":
                    _now_iso(),
            })
            .eq(
                "id",
                event_id,
            )
            .eq(
                "status",
                "open",
            )
            .execute()
        )

    return {
        "already_registered":
            False,

        "status":
            row["status"],

        "position_number":
            row["position_number"],

        "limit":
            limit,
    }
