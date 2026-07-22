import pyarrow as pa
import pyarrow.parquet as pq
import journal
from journal import schemas


def test_schema_version_is_1_1_0():
    assert schemas.SCHEMA_VERSION == "1.1.0"


def test_expected_tables_present():
    assert set(schemas.table_names()) == {
        "daily_state", "signals", "decisions", "order_plans",
        "fills", "positions", "trades",
    }


def test_every_table_has_mandatory_and_source_columns():
    required = set(schemas.MANDATORY_COLUMNS) | {"source_system"}
    for name in schemas.table_names():
        cols = set(schemas.get_schema(name).names)
        missing = required - cols
        assert not missing, f"{name} missing {missing}"


def test_trades_has_nullable_mfe_mae():
    sch = schemas.get_schema("trades")
    for col in ("mfe_pct", "mae_pct"):
        f = sch.field(col)
        assert f.nullable, f"{col} must be nullable"
        assert f.type == pa.float64()


def test_empty_table_keeps_schema():
    for name in schemas.table_names():
        empty = schemas.get_schema(name).empty_table()
        assert empty.num_rows == 0
        assert empty.schema == schemas.get_schema(name)
