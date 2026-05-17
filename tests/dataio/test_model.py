import numpy as np
import pandas as pd

from dataio.model import DatasetSchema, Scenario, TopologyDataset, DataIoError


def test_scenario_and_dataset_roundtrip():
    df = pd.DataFrame({"l_t1": [1.0, 2.0], "label": [0, 1]})
    sch = DatasetSchema(
        topology="ctown", tank_cols=["l_t1"], pump_status_cols=[],
        pump_flow_cols=[], junction_cols=[], column_map={"L_T1": "l_t1"},
    )
    sc = Scenario(name="test", frame=df, labels=np.array([0, 1]), attack_windows=[])
    ds = TopologyDataset(
        topology="ctown", calibration_frames=[df], eval_scenarios=[sc], schema=sch,
    )
    assert ds.topology == "ctown"
    assert ds.eval_scenarios[0].labels.tolist() == [0, 1]
    assert issubclass(DataIoError, Exception)
