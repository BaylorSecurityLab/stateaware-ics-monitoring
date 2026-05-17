"""Declarative anytown/ctown/ltown topology profiles (replace the subclasses)."""

from __future__ import annotations

from .model import StlError, TopologyProfile

ANYTOWN = TopologyProfile(
    name="anytown",
    tanks=["t41", "t42"],
    pumps=[78, 79],
    valves={},
    junctions=[],
    tank_physical={"t41": {"min": 0.0, "max": 10.668},
                   "t42": {"min": 0.0, "max": 10.668}},
    feeder_map={},
    pump_pressure_pairs={},
    control_rules=[("p78", "t41", 5.0, 8.0), ("p79", "t42", 5.0, 8.0)],
    symmetry_pairs=[("t41", "t42"), ("p78", "p79")],
    state_vars=["p78", "p79"],
    pump_status_fmt="p{pid}",
    pump_flow_fmt="f_p{pid}",
    hysteresis=2, smoothing_window=5, margin=0.05, min_fire_count=2,
)

CTOWN = TopologyProfile(
    name="ctown",
    tanks=[f"l_t{i}" for i in range(1, 8)],
    pumps=list(range(1, 12)),
    valves={"v2": {"status": "s_v2", "flow": "f_v2"}},
    junctions=["p_j280", "p_j269", "p_j300", "p_j256", "p_j289", "p_j415",
               "p_j302", "p_j306", "p_j307", "p_j317", "p_j14", "p_j422"],
    tank_physical={"l_t1": {"min": 0.0, "max": 6.5},
                   "l_t2": {"min": 0.0, "max": 5.9},
                   "l_t3": {"min": 0.0, "max": 6.75},
                   "l_t4": {"min": 0.0, "max": 4.7},
                   "l_t5": {"min": 0.0, "max": 4.5},
                   "l_t6": {"min": 0.0, "max": 5.5},
                   "l_t7": {"min": 0.0, "max": 5.0}},
    feeder_map={"l_t1": ["f_pu1", "f_pu2", "f_pu3"], "l_t2": ["f_v2"],
                "l_t3": ["f_pu4", "f_pu5"], "l_t4": ["f_pu6", "f_pu7"],
                "l_t5": ["f_pu8", "f_pu9"], "l_t7": ["f_pu10", "f_pu11"]},
    pump_pressure_pairs={1: ("p_j269", "p_j280"), 2: ("p_j269", "p_j280"),
                         4: ("p_j256", "p_j300"), 5: ("p_j256", "p_j300"),
                         6: ("p_j415", "p_j289"), 8: ("p_j306", "p_j302"),
                         10: ("p_j317", "p_j307")},
    control_rules=[("s_pu1", "l_t1", 4.0, 6.3), ("s_pu2", "l_t1", 1.0, 4.5),
                   ("s_pu4", "l_t3", 3.0, 5.3), ("s_pu5", "l_t3", 1.0, 3.5),
                   ("s_pu6", "l_t4", 2.0, 3.5), ("s_pu7", "l_t4", 3.0, 4.5),
                   ("s_pu8", "l_t5", 1.5, 4.0), ("s_pu10", "l_t7", 2.5, 4.8),
                   ("s_pu11", "l_t7", 1.0, 3.0), ("s_v2", "l_t2", 0.5, 5.5)],
    symmetry_pairs=[],
    state_vars=["s_pu2", "s_pu4", "s_pu7", "s_pu8", "s_pu10", "s_v2"],
    pump_status_fmt="s_pu{pid}",
    pump_flow_fmt="f_pu{pid}",
    hysteresis=2, smoothing_window=5, margin=0.05, min_fire_count=1,
)

LTOWN = TopologyProfile(
    name="ltown",
    tanks=["t1"],
    pumps=["pump_1"],
    valves={},
    junctions=[],
    tank_physical={"t1": {"min": 0.0, "max": 4.0}},
    feeder_map={"t1": ["f_pump_1"]},
    pump_pressure_pairs={},
    control_rules=[("pump_1", "t1", 2.4, 3.9)],
    symmetry_pairs=[],
    state_vars=["pump_1"],
    pump_status_fmt="{pid}",
    pump_flow_fmt="f_{pid}",
    mb_windows=(3, 6, 12),
    hysteresis=2, smoothing_window=5, margin=0.05, min_fire_count=2,
)

PROFILES = {"anytown": ANYTOWN, "ctown": CTOWN, "ltown": LTOWN}


def get_profile(name: str) -> TopologyProfile:
    try:
        return PROFILES[name]
    except KeyError as exc:
        raise StlError(f"unknown topology profile: {name}") from exc
