"""Calendario local de NYSE: nunca consulta un proveedor de precios."""
from datetime import datetime, timezone

import exchange_calendars as xcals
import pandas as pd


def market_is_open(now=None):
    instant = pd.Timestamp(now or datetime.now(timezone.utc))
    if instant.tzinfo is None:
        raise ValueError('La hora debe incluir zona horaria')
    calendar = xcals.get_calendar('XNYS')
    session = pd.Timestamp(instant.tz_convert('America/New_York').date())
    if not calendar.is_session(session):
        return False
    return calendar.session_open(session) <= instant < calendar.session_close(session)


if __name__ == '__main__':
    print('true' if market_is_open() else 'false')
