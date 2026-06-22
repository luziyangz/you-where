"""
共读域状态枚举（与 team/database-schema.md 一致）。
"""

# pairs.status
PAIR_STATUS_ACTIVE = "active"
PAIR_STATUS_UNBOUND = "unbound"

# books.status
BOOK_STATUS_READING = "reading"
BOOK_STATUS_FINISHED = "finished"
BOOK_STATUS_SWITCHED = "switched"

# book_switch_requests.status
SWITCH_REQUEST_PENDING = "pending"
SWITCH_REQUEST_APPROVED = "approved"
SWITCH_REQUEST_REJECTED = "rejected"

# 阅读历史 / 列表展示（由 book_history_display 产出）
DISPLAY_STATUS_FINISHED = "finished"
DISPLAY_STATUS_UNFINISHED = "unfinished"
DISPLAY_STATUS_SWITCHED = "switched"
