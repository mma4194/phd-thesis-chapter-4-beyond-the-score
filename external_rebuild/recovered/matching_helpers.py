def column_prefix(column: str) -> str:
    return column.split("__", 1)[0].lower() if "__" in column else ""

def infer_tier(column: str) -> str:
    prefix = column_prefix(column)
    if not prefix:
        return "other"
    if prefix in TIER_ALIASES:
        return TIER_ALIASES[prefix]
    for alias in sorted(TIER_ALIASES, key=len, reverse=True):
        suffix = prefix[len(alias):] if prefix.startswith(alias) else ""
        if suffix and suffix.isdigit():
            return TIER_ALIASES[alias]
    return "other"

def signal_class(column: str) -> str:
    """Semantic signal class used for capability breadth and balanced estimands."""
    value = column.lower()
    if column.endswith("__nonfinite_mask"):
        return "observability"
    if any(token in value for token in ("byte", "octet", "payload_len", "frame_len")):
        return "byte_volume"
    if any(token in value for token in (
        "mgmt", "management", "assoc", "deauth", "disassoc", "probe",
        "auth", "beacon", "channel", "permit_join", "route_request",
    )):
        return "management_control"
    if any(token in value for token in (
        "state", "event", "onoff", "open", "close", "motion", "occupancy",
        "switch", "contact", "presence", "alarm",
    )):
        return "state_event"
    if any(token in value for token in (
        "reset", "retrans", "retry", "lost", "drop", "error", "failure",
        "unreachable", "timeout", "duplicate_ack",
    )):
        return "reliability"
    if any(token in value for token in ("rssi", "lqi", "snr", "noise", "signal_strength")):
        return "radio_quality"
    if any(token in value for token in (
        "temperature", "humidity", "power", "voltage", "current", "energy",
        "pressure", "co2", "light", "illuminance",
    )):
        return "physical_context"
    if any(token in value for token in (
        "packet", "frame", "segment", "datagram", "count", "request", "response",
        "syn", "ack", "icmp", "dns", "tcp", "udp", "quic",
    )):
        return "packet_count"
    return "protocol_other"

def p0_block_profile(indices: np.ndarray) -> dict[str, float]:
    frame = CANON_DF.iloc[indices]
    profile: dict[str, float] = {}
    for tier in sorted(ACTIVE_TIERS):
        columns = [column for column in FEATURE_SCOPES["all_value_v3"] if infer_tier(column) == tier]
        if columns:
            values = frame[columns].to_numpy(dtype=np.float32)
            profile[f"tier_active__{tier}"] = float(np.mean(values != 0))
    for signal in sorted({signal_class(column) for column in P0_PROFILE_COLS}):
        columns = [column for column in P0_PROFILE_COLS if signal_class(column) == signal]
        if columns:
            values = frame[columns].to_numpy(dtype=np.float32)
            profile[f"signal_active__{signal}"] = float(np.mean(values != 0))
    for column in P0_PROFILE_COLS:
        values = frame[column].to_numpy(dtype=float)
        scale = max(robust_iqr(values), 1e-6)
        profile[f"mean__{column}"] = float(np.mean(values) / scale)
        profile[f"zero__{column}"] = float(np.mean(values == 0))
    seconds = time_sorted[indices]
    phase = (seconds % 86400.0) / 86400.0 * 2 * np.pi
    profile["tod_sin"] = float(np.mean(np.sin(phase)))
    profile["tod_cos"] = float(np.mean(np.cos(phase)))
    return profile

def match_p0_blocks(blocks: Sequence[np.ndarray]) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    profiles = [p0_block_profile(block) for block in blocks]
    columns = sorted(set().union(*(profile.keys() for profile in profiles)))
    matrix = np.asarray([[profile.get(column, 0.0) for column in columns] for profile in profiles], dtype=float)
    center = np.median(matrix, axis=0)
    scale = np.median(np.abs(matrix - center), axis=0) * 1.4826
    scale[scale < 1e-8] = 1.0
    z = (matrix - center) / scale
    midpoint = len(blocks) // 2
    left = list(range(midpoint))
    available_right = set(range(midpoint, len(blocks)))
    pairs: list[dict[str, Any]] = []
    for left_index in left:
        if not available_right:
            break
        right_index = min(
            available_right,
            key=lambda candidate: (float(np.linalg.norm(z[left_index] - z[candidate])), candidate),
        )
        available_right.remove(right_index)
        pairs.append({
            "pair_id": f"pair{len(pairs)}",
            "source_block": left_index,
            "target_block": right_index,
            "profile_distance": float(np.linalg.norm(z[left_index] - z[right_index])),
            "source_start": int(blocks[left_index][0]),
            "source_end": int(blocks[left_index][-1]) + 1,
            "target_start": int(blocks[right_index][0]),
            "target_end": int(blocks[right_index][-1]) + 1,
        })
        if len(pairs) >= int(CFG["p0_pairs"]):
            break
    if len(pairs) < 2:
        raise RuntimeError("Matched-block P0 produced fewer than two block pairs")
    calibration_count = max(1, int(round(len(pairs) * CFG["p0_calibration_fraction"])))
    calibration_count = min(calibration_count, len(pairs) - 1)
    pairs = sorted(pairs, key=lambda row: (row["profile_distance"], row["pair_id"]))
    # Balance profile distance across calibration and qualification. Assigning all
    # closest pairs to calibration would under-estimate natural real-to-real
    # variation and make the held-out qualification set systematically harder.
    calibration_indices = list(range(0, len(pairs), 2))[:calibration_count]
    if len(calibration_indices) < calibration_count:
        calibration_indices.extend(
            index for index in range(len(pairs))
            if index not in set(calibration_indices)
        )
        calibration_indices = calibration_indices[:calibration_count]
    calibration_indices = set(calibration_indices)
    for index, pair in enumerate(pairs):
        pair["phase"] = "calibration" if index in calibration_indices else "qualification"
    return pd.DataFrame(profiles), pairs
