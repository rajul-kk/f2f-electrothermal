"""Step a of the c4 dry: the solver against closed forms, before any PDNSim number (A21)."""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(__file__))
import irmesh  # noqa: E402


def chain(n_seg, r_seg):
    i = np.arange(n_seg)
    return i, i + 1, np.full(n_seg, 1 / r_seg)


def test_chain_with_equal_point_loads_matches_its_closed_form():
    # both ends at V0, current I drawn at each of the N-1 inner nodes: drop at node k = R I k (N - k) / 2, exactly
    n_seg, r, cur, v0 = 40, 0.37, 2e-4, 0.7
    i, j, g = chain(n_seg, r)
    sink = np.full(n_seg + 1, cur)
    sink[[0, n_seg]] = 0
    v, src = irmesh.solve(n_seg + 1, i, j, g, {0: v0, n_seg: v0}, sink)
    k = np.arange(n_seg + 1)
    assert np.allclose(v0 - v, r * cur * k * (n_seg - k) / 2, rtol=0, atol=1e-13)
    assert sum(src.values()) == pytest.approx(cur * (n_seg - 1))


def test_uniformly_loaded_strap_converges_to_the_continuum_parabola():
    # strap length L, width w, sheet rho, load j per um, both ends held: mid drop rho j L^2 / (8 w)
    L, w, rho, jl = 50.0, 0.5, 0.08, 1e-6
    exact = rho * jl * L**2 / (8 * w)
    errs = []
    for n_seg in (8, 32, 128):
        h = L / n_seg
        i, j = np.arange(n_seg), np.arange(1, n_seg + 1)
        g = irmesh.strap_conductance(np.full(n_seg, h), w, rho)
        sink = np.full(n_seg + 1, jl * h)
        sink[[0, n_seg]] = jl * h / 2
        v, _ = irmesh.solve(n_seg + 1, i, j, g, {0: 0.7, n_seg: 0.7}, sink)
        errs.append(abs((0.7 - v[n_seg // 2]) - exact) / exact)
    # lumped loads on a uniform chain are exact at the nodes for a uniform load, so only rounding is left: a 5e-5 V
    # drop read off 0.7 V carries about 1e-16 x 0.7 / 5e-5 per operation (seen: 2e-10 at 128 segments)
    assert all(e < 1e-8 for e in errs)


def grid(nx, ny, g):
    idx = np.arange(nx * ny).reshape(ny, nx)
    a = np.concatenate([idx[:, :-1].ravel(), idx[:-1, :].ravel()])
    b = np.concatenate([idx[:, 1:].ravel(), idx[1:, :].ravel()])
    return idx, a, b, np.full(len(a), g)


def test_mesh_matches_a_dense_solve_and_is_symmetric():
    idx, a, b, g = grid(9, 9, 3.0)
    n = idx.size
    fixed = {int(k): 0.7 for k in np.concatenate([idx[0], idx[-1], idx[:, 0], idx[:, -1]])}
    sink = np.zeros(n)
    sink[idx[4, 4]] = 1e-3
    v, _ = irmesh.solve(n, a, b, g, fixed, sink)
    G = irmesh.laplacian(n, a, b, g).toarray()
    free = np.setdiff1d(np.arange(n), list(fixed))
    fx = np.array(list(fixed))
    dense = np.linalg.solve(G[np.ix_(free, free)], -G[np.ix_(free, fx)] @ np.full(len(fx), 0.7) - sink[free])
    assert np.allclose(v[free], dense, atol=1e-14)
    assert v[idx[4, 2]] == pytest.approx(v[idx[2, 4]], abs=1e-15)   # the point load is at the centre
    assert v.min() == pytest.approx(v[idx[4, 4]])


def test_disconnected_part_and_bad_inputs_are_refused():
    with pytest.raises(ValueError, match="singular|not connected"):
        irmesh.solve(4, [0, 2], [1, 3], [1.0, 1.0], {0: 0.7}, np.zeros(4))
    with pytest.raises(ValueError, match="no fixed node"):
        irmesh.solve(2, [0], [1], [1.0], {}, np.zeros(2))
    with pytest.raises(ValueError, match="positive"):
        irmesh.strap_conductance(0.0, 1.0, 0.1)
