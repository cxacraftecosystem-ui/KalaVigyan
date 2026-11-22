from app.models import StateEnvValue
from app.services.state_values import STATE_SERIES_COLUMNS, state_values_sql

from ..contracts.golden import golden_text

STATE_REFRESH = "region.state-values.sql"


def test_the_geo_load_runs_the_refresh_the_backend_compiles() -> None:
    assert golden_text(STATE_REFRESH) == state_values_sql()


def test_the_refresh_fills_every_column_but_the_row_s_own_id_and_stamp() -> None:
    columns = {column.name for column in StateEnvValue.__table__.columns}
    assert set(STATE_SERIES_COLUMNS) == columns - {"id", "createdAt"}


def test_the_refresh_groups_only_the_stats_a_state_aggregates_and_skips_the_rock_type_twins() -> None:
    refresh = state_values_sql()
    assert "region_value.stat IN ('DISTRICT_MEAN', 'NORMAL', 'SHARE', 'DENSITY', 'TOTAL', 'COUNT'," in refresh
    assert "NOT LIKE 'lithology/_' || '%' ESCAPE '/'" in refresh
    assert refresh.count("WITH district_area AS MATERIALIZED") == 1
