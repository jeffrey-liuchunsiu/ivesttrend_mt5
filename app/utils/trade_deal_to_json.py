def make_serializable(obj):
    if isinstance(obj, dict):
        return {k: make_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [make_serializable(v) for v in obj]
    elif isinstance(obj, tuple):
        return tuple(make_serializable(v) for v in obj)
    elif hasattr(obj, '_asdict'):   # For namedtuples
        return make_serializable(obj._asdict())
    elif not isinstance(obj, (int, float, str, bool, type(None))):   # For any other non-serializable objects
        return str(obj)
    return obj

def trade_deals_to_json(trade_deals):
    trade_deals_dict = [make_serializable(trade_deal._asdict()) for trade_deal in trade_deals]
    return trade_deals_dict