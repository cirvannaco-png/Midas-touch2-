
def validate_signal(data: dict) -> tuple[bool, list[str] | None]:
    """
    Validate the canonical pre-trade setup contract.

    Legacy payloads may omit `invalidation`/`final_tp`; when present, the
    bridge enforces their relationship to entry, protective stop, TP1 and
    TP2 so the receiving side cannot persist a geometrically contradictory
    setup.
    """
    direction = data["direction"]
    entry = data["entry"]
    sl = data["sl"]
    tp1 = data["tp1"]
    tp2 = data["tp2"]
    invalidation = data.get("invalidation")
    final_tp = data.get("final_tp")
    errors: list[str] = []

    if direction == "BUY":
        if sl >= entry:
            errors.append("For BUY, stop loss must be below entry price")
        if tp1 <= entry:
            errors.append("For BUY, TP1 must be above entry price")
        if tp2 <= entry:
            errors.append("For BUY, TP2 must be above entry price")
        if tp2 <= tp1:
            errors.append("For BUY, TP2 must be above TP1")
        if invalidation is not None:
            if invalidation >= entry:
                errors.append("For BUY, thesis invalidation must be below entry price")
            if sl >= invalidation:
                errors.append("For BUY, protective stop must be below thesis invalidation")
        if final_tp is not None:
            if final_tp <= tp2:
                errors.append("For BUY, final TP must be above TP2")
    elif direction == "SELL":
        if sl <= entry:
            errors.append("For SELL, stop loss must be above entry price")
        if tp1 >= entry:
            errors.append("For SELL, TP1 must be below entry price")
        if tp2 >= entry:
            errors.append("For SELL, TP2 must be below entry price")
        if tp2 >= tp1:
            errors.append("For SELL, TP2 must be below TP1")
        if invalidation is not None:
            if invalidation <= entry:
                errors.append("For SELL, thesis invalidation must be above entry price")
            if sl <= invalidation:
                errors.append("For SELL, protective stop must be above thesis invalidation")
        if final_tp is not None:
            if final_tp >= tp2:
                errors.append("For SELL, final TP must be below TP2")

    if errors:
        return False, errors
    return True, None


def validate_trade_event(data: dict) -> tuple[bool, list[str] | None]:
    """
    Business rules for POST /trade payloads. SL/TP remain optional because a
    lifecycle event may legitimately omit levels after the position is flat.
    """
    direction = data["direction"]
    price = data["price"]
    sl = data.get("sl")
    tp1 = data.get("tp1")
    tp2 = data.get("tp2")
    errors: list[str] = []

    if direction == "BUY":
        if sl is not None and sl >= price:
            errors.append("For BUY, stop loss must be below price")
        if tp1 is not None and tp1 <= price:
            errors.append("For BUY, TP1 must be above price")
        if tp2 is not None and tp2 <= price:
            errors.append("For BUY, TP2 must be above price")
        if tp1 is not None and tp2 is not None and tp2 <= tp1:
            errors.append("For BUY, TP2 must be above TP1")
    elif direction == "SELL":
        if sl is not None and sl <= price:
            errors.append("For SELL, stop loss must be above price")
        if tp1 is not None and tp1 >= price:
            errors.append("For SELL, TP1 must be below price")
        if tp2 is not None and tp2 >= price:
            errors.append("For SELL, TP2 must be below price")
        if tp1 is not None and tp2 is not None and tp2 >= tp1:
            errors.append("For SELL, TP2 must be below TP1")

    if data["volume"] <= 0:
        errors.append("volume must be greater than 0")

    if errors:
        return False, errors
    return True, None
