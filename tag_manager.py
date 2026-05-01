# tag_manager.py - Tag management for sound samples

import os
import math
from params import PARAM_RANGES, NUM_PARAMS

TAGSPACE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tagspace.txt")

# Known tag categories with estimation rules
# Each rule: (tag_name, check_function)
TAG_RULES = [
    # Wave type
    ("square",     lambda p, wt: wt < 0.5),
    ("saw",        lambda p, wt: 0.5 <= wt < 1.5),
    ("sine",       lambda p, wt: 1.5 <= wt < 2.5),
    ("triangle",   lambda p, wt: 2.5 <= wt < 3.5),
    ("white",      lambda p, wt: 3.5 <= wt < 4.5),
    ("pink",       lambda p, wt: 4.5 <= wt < 5.5),
    ("brown",      lambda p, wt: 5.5 <= wt),
    # Duration
    ("blip",       lambda p, wt: p[3] + p[4] < 0.15),
    ("short",      lambda p, wt: p[3] + p[4] < 0.3),
    ("medium",     lambda p, wt: 0.3 <= p[3] + p[4] < 0.6),
    ("long",       lambda p, wt: p[3] + p[4] >= 0.6),
    # Volume
    ("soft",       lambda p, wt: p[2] < 0.3),
    ("loud",       lambda p, wt: p[2] > 0.7),
    # Pitch shift
    ("high",       lambda p, wt: p[10] > 0.5),
    ("low",        lambda p, wt: p[10] < -0.5),
    # Harmonics
    ("rich",       lambda p, wt: p[8] > 0.5),
    ("pure",       lambda p, wt: p[8] < 0.2),
    # Envelope
    ("punchy",     lambda p, wt: p[5] > 0.5 and p[3] < 0.3),
    ("smooth",     lambda p, wt: p[5] < 0.3),
]


def estimate_tags(params, wave_type):
    """Estimate tags based on parameters and wave type."""
    tags = []
    for tag_name, check_func in TAG_RULES:
        try:
            if check_func(params, wave_type):
                tags.append(tag_name)
        except Exception:
            pass
    return tags


def _normalize_param(value, param_index):
    """Normalize a parameter value to 0-1 range based on its defined range."""
    lo, hi, _ = PARAM_RANGES[param_index]
    if hi == lo:
        return 0.0
    return (value - lo) / (hi - lo)


def _param_distance(params_a, params_b):
    """Compute normalized Euclidean distance between two parameter sets."""
    if len(params_a) != len(params_b):
        return float('inf')
    sum_sq = 0.0
    for i in range(len(params_a)):
        norm_a = _normalize_param(params_a[i], i)
        norm_b = _normalize_param(params_b[i], i)
        diff = norm_a - norm_b
        sum_sq += diff * diff
    return math.sqrt(sum_sq / len(params_a))


def find_matching_tags(params, wave_type=None, top_n=3):
    """Scan database and find tags for most similar parameter sets.
    Returns list of (tag_string, similarity_score) tuples.
    """
    entries = _read_all_entries()
    if not entries:
        return []

    scored = []
    for entry in entries:
        entry_params_str = entry.get("PARAMS", "")
        if not entry_params_str:
            continue
        try:
            parts = entry_params_str.split(",")
            entry_params = [float(p) for p in parts]
        except (ValueError, AttributeError):
            continue

        if len(entry_params) != len(params):
            continue

        dist = _param_distance(params, entry_params)
        # Convert distance to similarity score (1.0 = identical, 0.0 = very different)
        # Using exponential decay: similarity = exp(-2 * distance)
        similarity = math.exp(-2.0 * dist)
        scored.append((entry.get("TAGS", ""), similarity, entry.get("SAMPLE", "")))

    # Sort by similarity descending
    scored.sort(key=lambda x: x[1], reverse=True)

    # Return top N matches with their tags and scores
    return [(tags, score) for tags, score, _ in scored[:top_n] if tags.strip()]


def _read_all_entries():
    """Read all entries from tagspace.txt."""
    entries = []
    if not os.path.exists(TAGSPACE_FILE):
        return entries
    current = {}
    with open(TAGSPACE_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if line == "---":
                if current:
                    entries.append(current)
                current = {}
            elif ":" in line:
                key, val = line.split(":", 1)
                current[key] = val
    if current:
        entries.append(current)
    return entries


def _params_match(entry_params, params):
    """Check if entry parameters match current params."""
    if not entry_params:
        return False
    parts = entry_params.split(",")
    if len(parts) != len(params):
        return False
    for a, b in zip(parts, params):
        try:
            if abs(float(a) - b) > 1e-6:
                return False
        except ValueError:
            return False
    return True


def save_tags(sample_id, params, tags_str, blend_t=None):
    """Save tags for a sample. Overwrite if params match."""
    entries = _read_all_entries()
    new_entries = []
    params_str = ",".join(str(p) for p in params)
    found = False
    for entry in entries:
        if (entry.get("SAMPLE") == sample_id and
                _params_match(entry.get("PARAMS", ""), params)):
            # Overwrite this entry
            found = True
            new_entry = {
                "SAMPLE": sample_id,
                "PARAMS": params_str,
                "TAGS": tags_str,
            }
            if blend_t is not None:
                new_entry["BLEND_T"] = str(blend_t)
            new_entries.append(new_entry)
        else:
            new_entries.append(entry)
    if not found:
        new_entry = {
            "SAMPLE": sample_id,
            "PARAMS": params_str,
            "TAGS": tags_str,
        }
        if blend_t is not None:
            new_entry["BLEND_T"] = str(blend_t)
        new_entries.append(new_entry)
    with open(TAGSPACE_FILE, "w") as f:
        for entry in new_entries:
            for k, v in entry.items():
                f.write(f"{k}:{v}\n")
            f.write("---\n")


def load_tags(sample_id, params, blend_t=None):
    """Load tags for a sample if params match."""
    entries = _read_all_entries()
    for entry in entries:
        if (entry.get("SAMPLE") == sample_id and
                _params_match(entry.get("PARAMS", ""), params)):
            return entry.get("TAGS", "")
    return ""


def _generate_random_params():
    """Generate random parameters within valid ranges."""
    import random
    params = []
    for i, (lo, hi, _) in enumerate(PARAM_RANGES):
        if i == 0 or i == 32:  # WaveType, WaveTypeB - integer
            params.append(float(random.randint(int(lo), int(hi))))
        else:
            params.append(random.uniform(lo, hi))
    return params


def generate_novel_params(num_candidates=500):
    """Generate parameters that are as far as possible from tagged latent space.
    Returns params with minimal similarity to any tagged entry.
    """
    entries = _read_all_entries()
    if not entries:
        return _generate_random_params()

    # Load all tagged parameter sets
    db_params = []
    for entry in entries:
        entry_params_str = entry.get("PARAMS", "")
        if not entry_params_str:
            continue
        try:
            parts = entry_params_str.split(",")
            entry_params = [float(p) for p in parts]
            if len(entry_params) == NUM_PARAMS:
                db_params.append(entry_params)
        except (ValueError, AttributeError):
            continue

    if not db_params:
        return _generate_random_params()

    # Generate candidates and find the one with highest minimum distance to DB
    best_params = None
    best_min_dist = -1

    for _ in range(num_candidates):
        candidate = _generate_random_params()
        # Compute minimum distance to any DB entry (we want to maximize this)
        min_dist = float('inf')
        for dp in db_params:
            dist = _param_distance(candidate, dp)
            if dist < min_dist:
                min_dist = dist

        if min_dist > best_min_dist:
            best_min_dist = min_dist
            best_params = candidate[:]

    return best_params if best_params else _generate_random_params()
