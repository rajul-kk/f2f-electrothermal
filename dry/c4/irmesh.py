"""Static IR drop on a resistive mesh (c4 dry, DESIGN.md): nodes joined by conductances, some nodes held at a supply
voltage, current drawn at others. One sparse solve of the reduced nodal equations G_ff v_f = -G_fx v_x - i_f.

Units throughout: um, ohm, A, V (converted once at load, A3).
"""
import warnings

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla


def strap_conductance(length_um, width_um, sheet_ohm_sq):
    """Conductance of a straight wire segment: width / (sheet resistance x length)."""
    length_um, width_um = np.asarray(length_um, float), np.asarray(width_um, float)
    if np.any(length_um <= 0) or np.any(width_um <= 0) or sheet_ohm_sq <= 0:
        raise ValueError("lengths, widths and sheet resistance must be positive")
    return width_um / (sheet_ohm_sq * length_um)


def laplacian(n, i, j, g):
    """n x n conductance matrix of edges (i[k], j[k], g[k]); parallel edges add."""
    i, j, g = np.asarray(i), np.asarray(j), np.asarray(g, float)
    if len(i) != len(j) or len(i) != len(g):
        raise ValueError("edge arrays differ in length")
    if np.any(g <= 0) or np.any(i == j):
        raise ValueError("edges need positive conductance and two distinct nodes")
    rows = np.concatenate([i, j, i, j])
    cols = np.concatenate([j, i, i, j])
    vals = np.concatenate([-g, -g, g, g])
    return sp.csr_matrix((vals, (rows, cols)), shape=(n, n))


def solve(n, i, j, g, fixed, sink):
    """Node voltages. `fixed`: {node: volts} (at least one per connected part); `sink`: length-n array of current
    drawn out of each node (A; negative injects). Returns (v, source_current) where source_current[k] is the current
    each fixed node supplies, so its sum equals the total sink (checked)."""
    sink = np.asarray(sink, float)
    if sink.shape != (n,):
        raise ValueError("sink must have one entry per node")
    if not fixed:
        raise ValueError("no fixed node: the voltages are not determined")
    G = laplacian(n, i, j, g)
    fx = np.fromiter(fixed, int)
    vx = np.fromiter(fixed.values(), float)
    free = np.setdiff1d(np.arange(n), fx)
    v = np.empty(n)
    v[fx] = vx
    if len(free):
        Gff = G[free][:, free].tocsc()
        rhs = -G[free][:, fx] @ vx - sink[free]
        with warnings.catch_warnings():
            warnings.simplefilter("error", spla.MatrixRankWarning)
            try:
                lu = spla.splu(Gff)
                x = lu.solve(rhs)
                x += lu.solve(rhs - Gff @ x)        # one step of iterative refinement (1 mOhm beside long rails)
                v[free] = x
            except (spla.MatrixRankWarning, RuntimeError):   # splu raises RuntimeError on an exactly singular matrix
                v[free] = np.nan
        if not np.all(np.isfinite(v[free])):
            raise ValueError("singular mesh: a part is not connected to any fixed node")
    supplied = G[fx] @ v + sink[fx]
    # A check on the solve, not on G: since G's columns sum to zero, the mismatch is the sum of the free rows'
    # residuals, each about eps x max|G| x max|v|; summed over n rows that grows like sqrt(n) (the Ibex VDD grid with
    # 1 mOhm pin edges: 4e-11 A over 633k rows). Allow 100x that, plus 1e-9 of the load.
    scale = 100 * np.finfo(float).eps * abs(G).max() * np.abs(v).max() * np.sqrt(n) + np.abs(sink).sum() * 1e-9
    if abs(supplied.sum() - sink.sum()) > scale + 1e-18:
        raise ValueError(f"current not conserved: supplied {supplied.sum()} A, drawn {sink.sum()} A")
    return v, dict(zip(fx.tolist(), supplied.tolist(), strict=True))
