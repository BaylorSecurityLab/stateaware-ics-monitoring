import numpy as np

from dataio.readers.ltown_layout import reshape_to_time_axis, detect_layout


def test_reshape_axis_time_vs_time_axis():
    n_axis, n_t = 3, 4
    flat = np.arange(n_axis * n_t, dtype=float)
    g_at = reshape_to_time_axis(flat, n_axis, n_t, "axis_time")
    assert g_at.shape == (n_t, n_axis)
    g_ta = reshape_to_time_axis(flat, n_axis, n_t, "time_axis")
    assert g_ta.shape == (n_t, n_axis)


def test_detect_layout_finds_tank_band():
    elev, maxlvl, n_t, n_nodes = 98.68, 4.0, 24, 5
    rng = np.random.default_rng(0)
    sims = []
    for _ in range(10):
        grid = rng.uniform(0, 50, size=(n_t, n_nodes))
        grid[:, 2] = elev + rng.uniform(0.1, maxlvl - 0.1, size=n_t)
        sims.append(grid.T.reshape(-1))
    arr = np.stack(sims)
    layout, tank_idx = detect_layout(arr, n_nodes, n_t)
    assert layout == "axis_time"
    assert tank_idx == 2


def test_detect_layout_uses_passed_tank_params_not_hardcoded():
    # Regression: real simgen tank elevation (63.09) / max-level (19.24)
    # differ from the historical hardcoded 98.68/4.0. detect_layout must
    # honor the passed tank_elevation_m/tank_max_level_m, not the constants.
    elev, maxlvl, n_t, n_nodes = 63.0936347, 19.24443401, 24, 6
    rng = np.random.default_rng(1)
    sims = []
    for _ in range(10):
        grid = rng.uniform(0, 40, size=(n_t, n_nodes))
        grid[:, 3] = elev + rng.uniform(0.1, maxlvl - 0.1, size=n_t)
        sims.append(grid.T.reshape(-1))
    arr = np.stack(sims)

    # With the stale hardcoded defaults the real tank is invisible.
    assert detect_layout(arr, n_nodes, n_t) == (None, None)

    # With the archive's true tank params it is found at node 3.
    layout, tank_idx = detect_layout(
        arr, n_nodes, n_t,
        tank_elevation_m=elev, tank_max_level_m=maxlvl,
    )
    assert layout == "axis_time"
    assert tank_idx == 3
