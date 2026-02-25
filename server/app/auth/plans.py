# # app/core/plans.py
# from datetime import date

# # 임시 구독 데이터 (DB 없이 시작)
# SUBSCRIPTIONS = {
#     "sk_live_demo": {
#         "plan": "pro",
#         "status": "active",       # active | cancelled
#         "expires_at": "2026-02-01"
#     },
#     "sk_free_demo": {
#         "plan": "free",
#         "status": "active",
#         "expires_at": None
#     }
# }

# def get_subscription(api_key: str | None):
#     if not api_key:
#         return None
#     return SUBSCRIPTIONS.get(api_key)

# def get_plan(api_key: str | None) -> str:
#     sub = get_subscription(api_key)
#     if not sub:
#         return "free"

#     if sub["expires_at"]:
#         if date.today() > date.fromisoformat(sub["expires_at"]):
#             return "free"

#     return sub["plan"]

# app/auth/plans.py

PLANS = {
    "free": {
        "name": "free",
        "rate_limit": 60,
        "include_volume": False,
    },
    "pro": {
        "name": "pro",
        "rate_limit": 600,
        "include_volume": True,
    },
}

if __name__ == "__main__":
    print("=== PLANS validation ===")

    assert "free" in PLANS
    assert "pro" in PLANS

    for name, plan in PLANS.items():
        assert "name" in plan
        assert "rate_limit" in plan
        assert "include_volume" in plan
        print(f"[OK] plan={name}", plan)

    print("PLANS validation OK")

