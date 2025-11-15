from typing import Any, Dict, List, Tuple
import math
import numpy as np
import pandas as pd

from app.core.distance import haversine


INF = 1e9


def compute_available_slots(capacity_tt: float, occupied_tt: float, max_load: float) -> int:
    """
    Hitung slot tambahan yang boleh diisi tanpa melewati max_load.
    floor(max_load * capacity) - occupied
    """
    cap_allow = int(math.floor(max_load * float(capacity_tt)))
    return max(0, cap_allow - int(math.floor(float(occupied_tt))))


def _compute_cost(distance_km: float, occ_ratio: float, weights: Dict[str, float], target_occ: float, radius_km: float) -> float:
    d_norm = min(distance_km, radius_km) / radius_km if radius_km > 0 else 1.0
    occ_penalty = max(0.0, occ_ratio - target_occ)
    return weights["wd"] * d_norm + weights["wo"] * occ_penalty  # wf reserved


def build_capacity_expanded_slots(
    facilities_df: "pd.DataFrame",
    weights: Dict[str, float],
    constraints: Dict[str, float],
) -> List[Dict[str, Any]]:
    """
    Buat daftar slot per RS untuk assignment berbasis Hungarian.
    Setiap slot mewakili "tempat tidur" yang boleh diisi (menjaga max_load).
    """
    slots: List[Dict[str, Any]] = []
    radius_km = constraints["radius_km"]
    max_load = constraints["max_load"]
    for _, rs in facilities_df.iterrows():
        rs_id = str(rs["id_rs"])
        cap = float(rs["capacity_tt"])
        occ = float(rs["occupied_tt"])
        if cap <= 0:
            continue
        # Berapa slot tambahan yang diizinkan?
        avail = compute_available_slots(capacity_tt=cap, occupied_tt=occ, max_load=max_load)
        if avail <= 0:
            continue
        for k in range(avail):
            # occ ratio "sebelum" mengisi slot-k
            occ_ratio_k = (occ + k) / cap
            slots.append(
                {
                    "hospital_id": rs_id,
                    "slot_index": k,
                    "occ_ratio_before": occ_ratio_k,
                    "lat": float(rs["lat"]),
                    "lon": float(rs["lon"]),
                    "services": str(rs.get("services", "")).lower(),
                    "cap": cap,
                    "occ0": occ,  # untuk hitung after
                    "kelas": rs.get("kelas"),
                    "wilayah": rs.get("wilayah"),
                }
            )
    return slots


def build_cost_matrix_with_capacity(
    patients_df: "pd.DataFrame",
    facilities_df: "pd.DataFrame",
    weights: Dict[str, float],
    constraints: Dict[str, float],
) -> Tuple[np.ndarray, List[int], List[Dict[str, Any]]]:
    """
    Bangun matriks biaya (patients x slots).
    - Baris: pasien
    - Kolom: slot RS (capacity-expanded)
    Entry biaya = INF jika tidak feasible (radius / layanan / slot tak tersedia).
    """
    radius_km = constraints["radius_km"]
    target_occ = constraints["target_occupancy"]

    slots = build_capacity_expanded_slots(facilities_df, weights, constraints)
    n_pat = len(patients_df)
    n_slot = len(slots)

    if n_pat == 0 or n_slot == 0:
        return np.zeros((n_pat, max(1, n_slot))), list(range(n_pat)), slots

    C = np.full((n_pat, n_slot), INF, dtype=float)
    pat_idx = list(range(n_pat))

    for i, (_, p) in enumerate(patients_df.iterrows()):
        plat = float(p["lat"])
        plon = float(p["lon"])
        case = str(p.get("kasus", "")).lower()

        for j, s in enumerate(slots):
            # layanan harus cocok
            if case and case not in s["services"]:
                continue
            # radius
            dist = haversine(plat, plon, s["lat"], s["lon"])
            if dist > radius_km:
                continue
            # biaya dengan occ ratio per-slot (approximate incremental occupancy)
            cost = _compute_cost(distance_km=dist, occ_ratio=s["occ_ratio_before"], weights=weights, target_occ=target_occ, radius_km=radius_km)
            C[i, j] = cost

    return C, pat_idx, slots


# ---------------- Hungarian Algorithm (square), pad if rectangular ---------------- #

def _hungarian_square(cost: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    Hungarian untuk matriks persegi. Mengembalikan (row_ind, col_ind).
    Implementasi sederhana O(n^3).
    """
    cost = cost.copy()
    n = cost.shape[0]

    # Step 1: Row reduction
    cost -= cost.min(axis=1, keepdims=True)
    # Step 2: Column reduction
    cost -= cost.min(axis=0, keepdims=True)

    # Helpers
    def _cover_zeros(c: np.ndarray):
        n = c.shape[0]
        # Greedy find independent zeros
        row_covered = np.zeros(n, dtype=bool)
        col_covered = np.zeros(n, dtype=bool)
        starred = np.zeros_like(c, dtype=bool)

        # Star zeros: choose one zero in each row if possible
        for i in range(n):
            for j in range(n):
                if c[i, j] == 0 and not row_covered[i] and not col_covered[j]:
                    starred[i, j] = True
                    row_covered[i] = True
                    col_covered[j] = True
                    break

        row_covered[:] = False
        col_covered[:] = False

        def cover_columns_with_starred_zeros():
            for j in range(n):
                if np.any(starred[:, j]):
                    col_covered[j] = True

        cover_columns_with_starred_zeros()

        while col_covered.sum() < n:
            # Find a noncovered zero and prime it
            # If no such zero, adjust matrix
            zero_found = True
            primed = np.zeros_like(c, dtype=bool)
            while True:
                r, s = -1, -1
                found = False
                for i in range(n):
                    if row_covered[i]:
                        continue
                    for j in range(n):
                        if not col_covered[j] and c[i, j] == 0:
                            r, s = i, j
                            found = True
                            break
                    if found:
                        break
                if not found:
                    # adjust matrix
                    uncovered = c[~row_covered][:, ~col_covered]
                    m = uncovered.min()
                    c[~row_covered] -= m
                    c[:, col_covered] += m
                else:
                    primed[r, s] = True
                    # If there is a starred zero in the row, cover row and uncover column
                    star_col = np.where(starred[r])[0]
                    if star_col.size:
                        j_star = star_col[0]
                        row_covered[r] = True
                        col_covered[j_star] = False
                        continue
                    else:
                        # Augmenting path:
                        # start from (r,s), alternate primed and starred zeros
                        path = [(r, s)]
                        # find star in column s
                        while True:
                            r_star = np.where(starred[:, path[-1][1]])[0]
                            if r_star.size == 0:
                                break
                            r2 = r_star[0]
                            path.append((r2, path[-1][1]))
                            # find prime in row r2
                            cands = np.where(primed[r2])[0]
                            if cands.size == 0:
                                break
                            j2 = cands[0]
                            path.append((r2, j2))
                        # flip stars along the path
                        for (ri, ci) in path:
                            if starred[ri, ci]:
                                starred[ri, ci] = False
                            else:
                                starred[ri, ci] = True
                        primed[:] = False
                        row_covered[:] = False
                        col_covered[:] = False
                        cover_columns_with_starred_zeros()
                        break  # back to while col_covered < n
        # Extract assignment
        row_ind = np.empty(n, dtype=int)
        col_ind = np.empty(n, dtype=int)
        for i in range(n):
            js = np.where(starred[i])[0]
            row_ind[i] = i
            col_ind[i] = js[0] if js.size else -1
        return row_ind, col_ind

    row_ind, col_ind = _cover_zeros(cost)
    return row_ind, col_ind


def linear_sum_assignment(cost: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    Versi yang menerima matriks persegi atau persegi panjang.
    Jika rectangular → pad ke matriks persegi dengan nilai 0 cost tambahan.
    """
    m, n = cost.shape
    if m == n:
        return _hungarian_square(cost)
    # pad ke persegi
    size = max(m, n)
    pad = np.zeros((size, size), dtype=float)
    pad[:m, :n] = cost
    # untuk baris/kolom dummy → tidak ingin dipilih, beri cost 0 saja,
    # nanti kita filter assignment > dimensi asli.
    row_ind, col_ind = _hungarian_square(pad)
    # kembalikan hanya pasangan di domain asli (baris < m dan kolom < n)
    mask = (row_ind < m) & (col_ind < n)
    return row_ind[mask], col_ind[mask]


def solve_hungarian_with_capacity(
    patients_df: "pd.DataFrame",
    facilities_df: "pd.DataFrame",
    weights: Dict[str, float],
    constraints: Dict[str, float],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Kembalikan (assignments, facilities_snapshot) berbasis Hungarian + capacity expansion.
    """
    C, pat_idx, slots = build_cost_matrix_with_capacity(patients_df, facilities_df, weights, constraints)
    if C.size == 0 or len(slots) == 0:
        return [], []

    # Jalankan Hungarian
    r_ind, c_ind = linear_sum_assignment(C)

    assignments: List[Dict[str, Any]] = []
    # copy untuk hitung occ_after per slot yang terpakai
    used_count_per_h: Dict[str, int] = {}

    radius_km = constraints["radius_km"]
    target_occ = constraints["target_occupancy"]
    for ri, ci in zip(r_ind, c_ind):
        cost = float(C[ri, ci])
        if cost >= INF:  # infeasible assignment → abaikan
            continue
        p = patients_df.iloc[ri]
        s = slots[ci]

        hid = s["hospital_id"]
        used_count_per_h[hid] = used_count_per_h.get(hid, 0) + 1

        # hitung distance lagi (tersedia di slots juga lat/lon)
        dist = haversine(float(p["lat"]), float(p["lon"]), s["lat"], s["lon"])
        occ_before = s["occ_ratio_before"]
        # after = (occ0 + k + 1)/cap , tapi karena beberapa slot bisa terambil di RS sama
        # safer: occ_after = (occ0 + total_used)/cap
        occ_after = (s["occ0"] + used_count_per_h[hid]) / s["cap"]

        assignments.append(
            {
                "patient_id": str(p["id_pasien"]),
                "hospital_id": hid,
                "distance_km": float(dist),
                "occ_before": float(occ_before),
                "occ_after": float(occ_after),
                "cost": float(cost),
            }
        )

    # Build facilities snapshot (occ akhir)
    # kita agregasi dari facilities_df + used_count_per_h
    facilities_snapshot: List[Dict[str, Any]] = []
    for _, rs in facilities_df.iterrows():
        rs_id = str(rs["id_rs"])
        cap = float(rs["capacity_tt"])
        occ0 = float(rs["occupied_tt"])
        add = float(used_count_per_h.get(rs_id, 0))
        occ = occ0 + add
        occ_ratio = occ / cap if cap > 0 else 0.0
        facilities_snapshot.append(
            {
                "hospital_id": rs_id,
                "capacity_tt": cap,
                "occupied_tt": occ,
                "occ_ratio": float(occ_ratio),
                "wilayah": rs.get("wilayah"),
                "kelas": rs.get("kelas"),
            }
        )

    return assignments, facilities_snapshot