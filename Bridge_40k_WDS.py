#!/usr/bin/env python3
"""Bridge_40k_WDS.py

Convert a BattleScribe/BSData (wh40k-11e) faction catalogue from ./Origin into the
WDS (Warhall) on-disk format under ./WDS/40k/<Faction>/.

Usage:
    python Bridge_40k_WDS.py [Faction]

Faction defaults to "Orks". The argument is matched against the Origin/*.json files
by stripping any "<Prefix> - " from the file stem (e.g. "Imperium - Adepta Sororitas"
-> "Adepta Sororitas", "Orks" -> "Orks").

Scope (per project decisions):
  * Emits: units.json, profiles.json, statlines.json, equipment.json, rules.json
  * Excludes: options / modifiedunit / modifiedprofile (wargear options) for now
  * All references resolved against a GLOBAL index built from every Origin/*.json
  * IDs reuse BattleScribe UUIDs with WDS prefixes; BaseId always ""; Formation always 3
"""

import argparse
import json
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ORIGIN_DIR = os.path.join(SCRIPT_DIR, "Origin")
WDS_DIR = os.path.join(SCRIPT_DIR, "WDS", "40k")

# Order and canonical keys for a unit statline (matches the reference output shape).
# InSv (invulnerable save) is folded into the statline instead of a separate rule.
UNIT_STAT_KEYS = ["M", "T", "SV", "W", "LD", "OC", "InSv"]
# Aliases used by BattleScribe characteristics -> canonical key above.
UNIT_STAT_ALIASES = {"M": "M", "T": "T", "SV": "SV", "SV.": "SV", "W": "W",
                     "LD": "LD", "OC": "OC", "INSV": "InSv"}
WEAPON_STAT_KEYS = ["Range", "A", "BS", "WS", "S", "AP", "D"]

WEAPON_TYPES = ("Ranged Weapons", "Melee Weapons")
ABILITY_TYPES = ("Abilities", "Psychic Abilities")
# Units carrying these bracketed labels are excluded from the bridge entirely.
EXCLUDED_LABEL_RE = re.compile(r"\[(legends?|crucible)\]", re.IGNORECASE)
# Some weapon profile names embed a rule as a trailing "(Rule: Info)" suffix,
# e.g. "Smash Hammer - Hunter (Hunter: MONSTER/VEHICLE)".
NAME_RULE_SUFFIX_RE = re.compile(r"\s*\(([^():]+):\s*([^()]+)\)\s*$")
# Selection groups that aren't wargear; the option walker doesn't descend into them.
NON_WARGEAR_GROUPS = {"weapon modifications", "crusade", "enhancements",
                      "enhancements - upgrades", "warlord", "detachment"}


# ---------------------------------------------------------------------------
# Loading / indexing
# ---------------------------------------------------------------------------

def load_catalogues(origin_dir):
    """Return {path: root_dict} for every JSON file in the Origin folder."""
    cats = {}
    for name in os.listdir(origin_dir):
        if not name.lower().endswith(".json"):
            continue
        path = os.path.join(origin_dir, name)
        with open(path, "r", encoding="utf-8") as fh:
            cats[name] = json.load(fh)
    return cats


def build_index(catalogues):
    """Build a global id -> object index and a name -> rule-description map."""
    index = {}
    rule_text = {}
    known_bases = {}  # lowercased canonical name/alias -> canonical display name (USRs)

    def walk(node):
        if isinstance(node, dict):
            node_id = node.get("id")
            if isinstance(node_id, str):
                index.setdefault(node_id, node)
            name = node.get("name")
            desc = node.get("description")
            if isinstance(name, str) and isinstance(desc, str):
                rule_text.setdefault(name.strip().lower(), desc)
            # Universal Special Rules carry an 'alias' list; record their canonical names.
            alias = node.get("alias")
            if isinstance(name, str) and isinstance(alias, list):
                known_bases.setdefault(name.strip().lower(), name.strip())
                for a in alias:
                    if isinstance(a, str) and a.strip():
                        known_bases.setdefault(a.strip().lower(), name.strip())
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    for data in catalogues.values():
        walk(data)
    return index, rule_text, known_bases


def catalogue_root(data):
    """Return the inner catalogue/gameSystem object of an Origin file."""
    return data.get("catalogue") or data.get("gameSystem") or data


def resolve_faction(catalogues, faction_arg):
    """Return (faction_name, catalogue_root) for the requested faction."""
    wanted = faction_arg.strip().lower()
    for name, data in catalogues.items():
        stem = os.path.splitext(name)[0]
        short = stem.split(" - ")[-1]
        if short.strip().lower() == wanted or stem.strip().lower() == wanted:
            return short.strip(), catalogue_root(data)
    return None, None


def is_excluded_labeled(name):
    return isinstance(name, str) and EXCLUDED_LABEL_RE.search(name) is not None


# ---------------------------------------------------------------------------
# Tree helpers
# ---------------------------------------------------------------------------

def find_units(catalogue, index):
    """Collect roster units by resolving the catalogue's root entryLinks.

    A roster entry is a selectionEntry of type 'unit' (multi-model) or 'model'
    (single-model character) that exposes a 'Unit' stat profile.
    """
    units = []
    seen = set()

    def consider(entry, source_name=None):
        if not entry or entry.get("type") not in ("unit", "model"):
            return
        if is_excluded_labeled(source_name) or is_excluded_labeled(entry.get("name")):
            return
        eid = entry.get("id")
        if eid in seen:
            return
        if unit_profile_of(entry, index) is None and not find_models(entry):
            return
        seen.add(eid)
        units.append(entry)

    for link in catalogue.get("entryLinks", []) or []:
        consider(index.get(link.get("targetId")), link.get("name"))

    # Fallback: any directly-defined unit not reached through a root entryLink.
    def walk(node):
        if isinstance(node, dict):
            if node.get("type") == "unit":
                consider(node)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(catalogue)
    return units


def model_base_name(name):
    """Strip a ' w/ <loadout>' suffix BattleScribe appends to weapon-variant models."""
    if not name:
        return name
    idx = name.lower().find(" w/ ")
    return name[:idx].strip() if idx != -1 else name.strip()


def model_max_constraint(entry):
    """Largest parent-scoped 'max' constraint on a model (its squad-slot quota)."""
    best = 0
    for c in entry.get("constraints", []) or []:
        if c.get("type") == "max" and c.get("scope") == "parent":
            try:
                best = max(best, int(c.get("value", 0)))
            except (TypeError, ValueError):
                continue
    return best


def find_models(unit):
    """Collect (default_model, [other_variants]) per role in a unit.

    A "X w/ Y" name always means "base profile X, with weapon option Y" -
    BattleScribe lists these as separate 'model' siblings that all resolve to
    the same underlying stat profile (e.g. 'Beast Snagga Boy' and 'Beast
    Snagga Boy w/ Thump gun' both link to the same profile; all 5 'Kommandos
    w/ <weapon>' variants share the same 'Kommando' profile). Within each
    base-name group, the bare (unsuffixed) sibling is the default; if none
    exists, the enclosing group's 'defaultSelectionEntryId' (e.g. Warbuggies,
    where every sibling is already named "w/ <weapon>" and none is bare) wins;
    failing that, the sibling with the largest 'max' constraint (its usual
    squad-slot quota) is used. The other variants aren't linked into the
    profile but their weapons are still returned so they can be pre-catalogued
    in equipment.json for a future WDS options pass.
    """
    grouped = {}  # base name -> [model, ...]
    order = []
    group_default = {}  # base name -> id of the enclosing group's declared default

    def walk(node):
        if isinstance(node, dict):
            if node is not unit and node.get("type") == "model":
                return  # do not descend into a model's own sub-models
            own_default = node.get("defaultSelectionEntryId")
            entries = node.get("selectionEntries")
            if isinstance(entries, list):
                for item in entries:
                    if isinstance(item, dict) and item.get("type") == "model":
                        # Group by base name across the whole unit - BattleScribe may
                        # place a 'X w/ <weapon>' variant in a separate group (e.g. Boyz'
                        # 'Boy w/ Big shoota' under a 'Special Weapons' group) rather than
                        # as a direct sibling of the plain 'X' model.
                        key = model_base_name(item.get("name", ""))
                        if key not in grouped:
                            grouped[key] = []
                            order.append(key)
                        grouped[key].append(item)
                        if own_default and item.get("id") == own_default:
                            group_default[key] = own_default
                    else:
                        walk(item)
            for key, value in node.items():
                if key != "selectionEntries":
                    walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(unit)

    def pick_default(key, variants):
        default_id = group_default.get(key)
        if default_id:
            for v in variants:
                if v.get("id") == default_id:
                    return v
        for v in variants:
            if v.get("name", "").strip() == model_base_name(v.get("name", "")):
                return v  # exact, unsuffixed match
        return max(variants, key=model_max_constraint)

    result = []
    for key in order:
        variants = grouped[key]
        default = pick_default(key, variants)
        others = [v for v in variants if v is not default]
        result.append((default, others))
    return result


def chars_to_dict(profile):
    out = {}
    for ch in profile.get("characteristics", []) or []:
        out[ch.get("name", "")] = ch.get("$text", "") or ""
    return out


def unit_profile_of(entry, index):
    """Return the first 'Unit' typeName profile for an entry (inline or infoLink)."""
    for prof in entry.get("profiles", []) or []:
        if prof.get("typeName") == "Unit":
            return prof
    for link in entry.get("infoLinks", []) or []:
        target = index.get(link.get("targetId"))
        if target and target.get("typeName") == "Unit":
            return target
    return None


def link_append_value(link):
    """BattleScribe stores per-instance rule values (e.g. Deadly Demise -> 1) as a
    {field:'name', type:'append', value:X} modifier on the infoLink, not on the
    target rule. Extract that value, if present, as a string."""
    for mod in link.get("modifiers", []) or []:
        if mod.get("field") == "name" and mod.get("type") == "append":
            return str(mod.get("value", "")).strip() or None
    return None


def has_conditional_hidden(node):
    """True if a modifiers array can hide this node based on other roster choices
    (e.g. Weirdboy's 'Roar of Mork' is only granted with a 'Wurrband' selection).
    Such abilities aren't guaranteed baseline content, so they're registered as
    rules but not linked into the default profile (a future WDS option)."""
    for mod in node.get("modifiers", []) or []:
        if mod.get("field") == "hidden" and (mod.get("conditions") or mod.get("conditionGroups")):
            return True
    return False


def ability_profiles_of(entry, index):
    """Return (profile_or_rule, info, included) tuples attached to an entry.

    info carries the per-instance value appended via a BattleScribe link modifier
    (e.g. Deadly Demise -> '1'), or None when the rule has no such value.
    included is False for abilities gated by a conditional 'hidden' modifier;
    callers should still register these as rules but skip linking them.
    """
    result = []
    for prof in entry.get("profiles", []) or []:
        if prof.get("typeName") in ABILITY_TYPES:
            result.append((prof, None, not has_conditional_hidden(prof)))
    for link in entry.get("infoLinks", []) or []:
        target = index.get(link.get("targetId"))
        if not target:
            continue
        # Accept both profile types (Abilities/Psychic) and rule objects
        if target.get("typeName") in ABILITY_TYPES or target.get("description"):
            included = not (has_conditional_hidden(link) or has_conditional_hidden(target))
            result.append((target, link_append_value(link), included))
    return result


def is_mandatory_entry(entry, default_id=None):
    """A selectionEntry/entryLink is fixed/default gear when it carries an explicit
    min>=1 constraint, or when its enclosing group names it as the default via
    'defaultSelectionEntryId' (many nested wargear choices, e.g. a Nob's Kustom
    Choppa/Kombi-skorcha, carry no constraints of their own - only the enclosing
    group does, naming its default child instead). BattleScribe defaults an
    omitted min to 0 (optional swap/upgrade), which we skip for later WDS options."""
    if default_id is not None:
        return entry.get("id") == default_id
    for c in entry.get("constraints", []) or []:
        if c.get("type") == "min" and c.get("value", 0) >= 1:
            return True
    return False


def weapon_profiles_of(entry, index):
    """Return (weapon_profile, mandatory) pairs for gear found under a model.

    Recurses through selectionEntries, selectionEntryGroups and entryLinks nested
    under the model (BattleScribe wraps mandatory wargear, e.g. the Rukkatrukk
    Squigbuggy's Sawn-off Shotgun/Squig Launchas/Saw Blades, inside a "Wargear"
    selectionEntryGroup). Every weapon found is returned so its Equipment/Statline
    data is still catalogued; 'mandatory' is False for optional swaps/upgrades
    (no explicit min>=1 constraint, or nested under one), reserved for a future
    WDS options pass and thus not linked into a Profile's default Children.
    Recursion stops at nested 'model' entries so sub-models' gear isn't pulled in.
    """
    found = {}  # weapon id -> [profile, mandatory]
    visited = set()

    def add_from(node, mandatory):
        for prof in node.get("profiles", []) or []:
            if prof.get("typeName") in WEAPON_TYPES:
                wid = prof.get("id")
                if wid in found:
                    if mandatory:
                        found[wid][1] = True
                else:
                    found[wid] = [prof, mandatory]

    def walk(node, mandatory, default_id=None):
        if not node or id(node) in visited:
            return
        visited.add(id(node))
        if node is not entry and node.get("type") == "model":
            return  # do not pull weapons from a nested sub-model
        add_from(node, mandatory)
        for link in node.get("entryLinks", []) or []:
            walk(index.get(link.get("targetId")), mandatory and is_mandatory_entry(link, default_id))
        for sub in node.get("selectionEntries", []) or []:
            walk(sub, mandatory and is_mandatory_entry(sub, default_id))
        for group in node.get("selectionEntryGroups", []) or []:
            # Groups aren't gated themselves; their children are, using this group's
            # own defaultSelectionEntryId (reset per level) or their own constraints.
            walk(group, mandatory, default_id=group.get("defaultSelectionEntryId"))

    walk(entry, True)
    for link in entry.get("infoLinks", []) or []:
        target = index.get(link.get("targetId"))
        if target:
            add_from(target, True)
    return [(prof, mandatory) for prof, mandatory in found.values()]


def option_profiles_of(entry, index, types):
    """Profiles of the given typeName set representing a single wargear choice - one
    level only, not descending into nested selectionEntryGroups (used to build
    option add/remove sets)."""
    profs = []
    seen = set()

    def add(node):
        if not node:
            return
        for p in node.get("profiles", []) or []:
            if p.get("typeName") in types and p.get("id") not in seen:
                seen.add(p.get("id"))
                profs.append(p)

    add(entry)
    for link in entry.get("entryLinks", []) or []:
        add(index.get(link.get("targetId")))
    for sub in entry.get("selectionEntries", []) or []:
        add(sub)
    return profs


def option_weapon_profiles(entry, index):
    return option_profiles_of(entry, index, WEAPON_TYPES)


def option_ability_profiles(entry, index):
    return option_profiles_of(entry, index, ABILITY_TYPES)


def option_weapon_counts(entry, index):
    """Map weapon-profile id -> quantity for a model's direct wargear entries (one
    level), so e.g. 'two Busta Rokkit Launchas' can be distinguished from one."""
    counts = {}

    def qty_of(node):
        for c in node.get("constraints", []) or []:
            if c.get("type") == "max":
                try:
                    return max(1, int(c.get("value", 1)))
                except (TypeError, ValueError):
                    pass
        return 1

    def note(node, count):
        for p in node.get("profiles", []) or []:
            if p.get("typeName") in WEAPON_TYPES:
                counts[p["id"]] = counts.get(p["id"], 0) + count

    for link in entry.get("entryLinks", []) or []:
        target = index.get(link.get("targetId"))
        if target:
            note(target, qty_of(link))
    for sub in entry.get("selectionEntries", []) or []:
        note(sub, qty_of(sub))
    return counts


# ---------------------------------------------------------------------------
# Conversion
# ---------------------------------------------------------------------------

def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.strip().lower()).strip("-")


def _clean_rule_value(rest):
    """Trim separators/parens off the value portion split from a rule name."""
    rest = (rest or "").strip()
    while rest[:1] in (":", "-"):
        rest = rest[1:].strip()
    if rest.startswith("(") and rest.endswith(")"):
        rest = rest[1:-1].strip()
    return rest or None


# Trailing value token: save (6+), plain number (2), dice (D3, 2D6, D6+1), or literal X.
_RULE_VALUE_TOKEN_RE = re.compile(r"^(.*?)\s+([0-9]+\+|[0-9]*D[0-9]+(?:\+[0-9]+)?|[0-9]+|X)$")


def split_rule_name_value(raw, known_bases=None):
    """Separate a rule display name into (base_name, value).

    Layer 1 uses the game-system's canonical USR names/aliases (known_bases) so
    'Feel No Pain 6+' -> ('Feel No Pain', '6+') and
    'LETHAL HITS: non-MONSTER/VEHICLE' -> ('Lethal Hits', 'non-MONSTER/VEHICLE').
    Layer 2 falls back to syntax (trailing parenthetical, value token, or colon)
    for faction abilities, e.g. 'Roar of Mork (psychic level 1)'. value is None
    when no value part is present.
    """
    raw = (raw or "").strip()
    if not raw:
        return raw, None

    # Layer 1: longest canonical base that the name equals or starts with.
    low = raw.lower()
    best_key = None
    for key in (known_bases or {}):
        if low == key or low.startswith(key + " ") or low.startswith(key + ":") \
                or low.startswith(key + "(") or low.startswith(key + "-"):
            if best_key is None or len(key) > len(best_key):
                best_key = key
    if best_key is not None:
        return known_bases[best_key], _clean_rule_value(raw[len(best_key):])

    # Layer 2a: trailing parenthetical annotation.
    m = re.search(r"\s*\(([^()]*)\)\s*$", raw)
    if m:
        return raw[:m.start()].strip(), (m.group(1).strip() or None)
    # Layer 2b: trailing value token.
    m = _RULE_VALUE_TOKEN_RE.match(raw)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    # Layer 2c: colon-separated qualifier.
    if ": " in raw:
        head, _, tail = raw.partition(":")
        return head.strip(), (tail.strip() or None)
    return raw, None


def split_name_rule_suffix(name):
    """Split a trailing '(Rule: Info)' annotation out of a weapon profile name.

    Returns (clean_name, rule_name, info); rule_name/info are None if absent.
    """
    m = NAME_RULE_SUFFIX_RE.search(name or "")
    if not m:
        return name, None, None
    return name[:m.start()].strip(), m.group(1).strip(), m.group(2).strip()


def make_statline(profile, keys, alias=None):
    """Build a WDS statline dict from a BattleScribe stat profile."""
    raw = chars_to_dict(profile)
    upper = {k.upper(): v for k, v in raw.items()}
    attrs = {}
    for key in keys:
        val = upper.get(key.upper())
        # Blank characteristics (e.g. no invulnerable save) are omitted rather than stored empty
        if val:
            attrs[key] = val
    return attrs


def load_existing_lookup(path):
    """Return {(Name, Type): Id} for entries already on disk, or {} if absent/unreadable.

    Lets re-running the bridge (or bridging a faction with pre-existing hand-curated
    data, e.g. Adepta Sororitas' sequential statline_N/rule_N ids) reuse whatever Id
    is already assigned to a same-named entry instead of minting a new one.
    """
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}
    lookup = {}
    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            name, typ, item_id = item.get("Name"), item.get("Type"), item.get("Id")
            if name and typ and item_id:
                lookup.setdefault((name, typ), item_id)  # first match wins on duplicate names
    return lookup


def load_existing_ids(out_dir):
    """Load the (Name, Type) -> Id maps for every output file in a faction folder."""
    return {
        "units": load_existing_lookup(os.path.join(out_dir, "units.json")),
        "profiles": load_existing_lookup(os.path.join(out_dir, "profiles.json")),
        "statlines": load_existing_lookup(os.path.join(out_dir, "statlines.json")),
        "equipment": load_existing_lookup(os.path.join(out_dir, "equipment.json")),
        "rules": load_existing_lookup(os.path.join(out_dir, "rules.json")),
        "options": load_existing_lookup(os.path.join(out_dir, "options.json")),
    }


class Converter:
    def __init__(self, index, rule_text, existing=None, known_bases=None):
        self.index = index
        self.rule_text = rule_text
        self.known_bases = known_bases or {}
        self.existing = existing or {}
        self._id_cache = {}    # category -> {fallback_id: resolved_id}
        self._claimed = {}     # category -> set of existing ids already reused
        self._content_fp = {}  # category -> {content_fingerprint: id} for in-run dedup
        self.statlines = {}   # id -> statline entry
        self.rules = {}       # id -> rule entry
        self.equipment = {}   # id -> equipment entry
        self.profiles = {}    # id -> profile entry
        self.units = []       # ordered unit entries
        self.hierarchy = {}   # role -> [unit ids]
        self.options = {}            # id -> option entry
        self.modified_units = []     # WDSOptionModifiedUnit records
        self.modified_profiles = []  # WDSOptionModifiedProfile records
        self._modrec_seen = set()    # dedup key for modified* records

    def _reuse_id(self, category, name, type_, fallback_id):
        """Reuse an existing on-disk Id for a same (Name, Type) entry, else fallback.

        Memoized by the stable fallback_id so the same source always resolves to the
        same Id, and each existing Id is handed out at most once so distinct items
        sharing a name aren't collapsed together.
        """
        cache = self._id_cache.setdefault(category, {})
        if fallback_id in cache:
            return cache[fallback_id]
        claimed = self._claimed.setdefault(category, set())
        existing_id = self.existing.get(category, {}).get((name, type_))
        if existing_id is not None and existing_id not in claimed:
            claimed.add(existing_id)
            resolved = existing_id
        else:
            resolved = fallback_id
        cache[fallback_id] = resolved
        return resolved

    def _dedup_content(self, category, fingerprint, candidate_id):
        """Reuse the Id of an already-registered entry with identical content.

        Origin often defines the same item (e.g. 'Slugga') under multiple distinct
        UUIDs with byte-identical stats/rules; this collapses them onto one Id
        instead of emitting duplicates. Returns the Id to actually use.
        """
        cache = self._content_fp.setdefault(category, {})
        return cache.setdefault(fingerprint, candidate_id)

    # -- rule helpers ------------------------------------------------------
    def _register_rule(self, base_name, description, fallback_id):
        """Create/reuse a rule entry keyed by its base name; return its Id."""
        rid = self._reuse_id("rules", base_name, "Rule", fallback_id)
        rid = self._dedup_content("rules", (base_name, description or ""), rid)
        if rid not in self.rules:
            self.rules[rid] = {
                "Id": rid,
                "Name": base_name,
                "Type": "Rule",
                "Description": description or "",
            }
        return rid

    def add_ability_rule(self, prof):
        """Return (rid, value); value-bearing rules consolidate under their base name."""
        base, value = split_rule_name_value(prof.get("name", ""), self.known_bases)
        chars = chars_to_dict(prof)
        desc = chars.get("Description") or " ".join(v for v in chars.values() if v)
        fallback = "rule_kw_" + slug(base) if value else "rule_" + prof["id"]
        return self._register_rule(base, desc, fallback), value

    def add_rule(self, rule_obj):
        """Add a shared rule object; return (rid, value)."""
        base, value = split_rule_name_value(rule_obj.get("name", ""), self.known_bases)
        desc = rule_obj.get("description", "")
        if not desc:
            desc = self.rule_text.get(base.lower(), "")
        fallback = "rule_kw_" + slug(base) if value else "rule_" + rule_obj["id"]
        return self._register_rule(base, desc, fallback), value

    def add_keyword_rule(self, keyword):
        """Split a weapon keyword into (rid, value), e.g. 'RAPID FIRE 1' -> value '1'."""
        raw = keyword.strip()
        if not raw:
            return None, None
        base, value = split_rule_name_value(raw, self.known_bases)
        desc = self.rule_text.get(base.lower(), "")
        return self._register_rule(base, desc, "rule_kw_" + slug(base)), value

    def add_named_rule(self, name):
        """Register a rule from a weapon-name suffix; returns its Id."""
        base, _ = split_rule_name_value(name, self.known_bases)
        desc = self.rule_text.get(base.lower(), "")
        return self._register_rule(base, desc, "rule_kw_" + slug(base))

    # -- weapon/equipment --------------------------------------------------
    def add_weapon(self, prof):
        name, rule_name, rule_info = split_name_rule_suffix(prof.get("name", ""))
        equip_id = self._reuse_id("equipment", name, "Equipment", prof["id"])
        if equip_id in self.equipment:
            return equip_id

        attrs = make_statline(prof, WEAPON_STAT_KEYS)
        statline_id = self._reuse_id("statlines", name, "Statline", "statline_" + prof["id"])
        statline_fp = (name, tuple(sorted(attrs.items())))
        statline_id = self._dedup_content("statlines", statline_fp, statline_id)
        if statline_id not in self.statlines:
            self.statlines[statline_id] = {
                "Id": statline_id,
                "Name": name,
                "Type": "Statline",
                "Attributes": attrs,
            }

        children = [{"Id": statline_id}]
        if rule_name:
            ref = {"Id": self.add_named_rule(rule_name)}
            if rule_info:
                ref["Info"] = rule_info
            children.append(ref)
        keywords = chars_to_dict(prof).get("Keywords", "")
        for kw in (k for k in keywords.split(",") if k.strip()):
            rid, info = self.add_keyword_rule(kw)
            if rid:
                ref = {"Id": rid}
                if info:
                    ref["Info"] = info
                children.append(ref)

        children_fp = tuple((c["Id"], c.get("Info")) for c in children)
        equip_id = self._dedup_content("equipment", (name, children_fp), equip_id)
        if equip_id in self.equipment:
            return equip_id
        self.equipment[equip_id] = {
            "Id": equip_id,
            "Name": name,
            "Type": "Equipment",
            "Children": children,
        }
        return equip_id

    # -- options -----------------------------------------------------------
    def collect_weapon_options(self, owner, unit_id, profile_id, single_profile):
        """Emit wargear options from a model's selection groups.

        A group with a 'defaultSelectionEntryId' is a swap: each non-default child
        becomes an option that adds its weapon and removes the group's default.
        Groups/entries without a default are additive: optional (no min>=1) entries
        become add-only options (empty remove set). Mandatory entries are base gear
        (already linked into the profile) and are only descended into for nested groups.
        Swap groups are often nested inside an outer 'Wargear' group, so every node's
        own selectionEntryGroups are recursed into regardless of depth.
        """
        specs = []  # (source_entry, add_profs, remove_profs)
        visited = set()

        def process(node):
            if not node or id(node) in visited:
                return
            visited.add(id(node))
            if node is not owner and node.get("type") == "model":
                return  # stay within this model
            if node.get("name", "").strip().lower() in NON_WARGEAR_GROUPS:
                return  # skip crusade / detachment / weapon-modification sub-trees

            children = [(link, self.index.get(link.get("targetId")))
                        for link in node.get("entryLinks", []) or []]
            children += [(sub, sub) for sub in node.get("selectionEntries", []) or []]
            default_id = node.get("defaultSelectionEntryId")
            default = None
            if default_id and default_id != "none":
                default = next((c for c in children if c[0].get("id") == default_id
                                or (c[1] and c[1].get("id") == default_id)), None)

            if default is not None:
                remove_profs = option_weapon_profiles(default[1] or default[0], self.index)
                for src, target in children:
                    node_t = target or src
                    if src is default[0]:
                        process(node_t)  # descend into the default for deeper groups
                    else:
                        adds = option_weapon_profiles(node_t, self.index)
                        if adds:
                            specs.append((src, adds, remove_profs))
            else:
                for src, target in children:
                    node_t = target or src
                    adds = option_weapon_profiles(node_t, self.index)
                    if not adds:
                        process(node_t)
                    elif is_mandatory_entry(src):
                        process(node_t)  # base gear; descend for nested option groups
                    else:
                        specs.append((src, adds, []))

            for group in node.get("selectionEntryGroups", []) or []:
                process(group)

        process(owner)
        for source, add_profs, remove_profs in specs:
            self._emit_weapon_option(source, add_profs, remove_profs, unit_id, profile_id, single_profile)

    def emit_variant_option(self, variant, default_owner, unit_id, profile_id, single_profile):
        """Turn a model-count-limited special-weapon variant (find_models' 'others',
        e.g. 'Boy w/ Big shoota') into an option. Diffs against the default by:
        - weapon quantity (e.g. 'Two Busta Rokkit Launchas' adds a 2nd copy of a
          weapon the default already has once - a same-id weapon can't be detected
          by identity alone, so counts are compared), and
        - added abilities (e.g. 'Pulsa rokkit' adds only an ability, no new weapon).
        """
        default_counts = option_weapon_counts(default_owner, self.index)
        variant_counts = option_weapon_counts(variant, self.index)
        default_by_id = {p["id"]: p for p in option_weapon_profiles(default_owner, self.index)}
        variant_by_id = {p["id"]: p for p in option_weapon_profiles(variant, self.index)}

        add_profs = [p for wid, p in variant_by_id.items()
                     if variant_counts.get(wid, 1) > default_counts.get(wid, 0)]
        remove_profs = [p for wid, p in default_by_id.items()
                        if variant_counts.get(wid, 0) < default_counts.get(wid, 1)]

        default_ab_ids = {p["id"] for p in option_ability_profiles(default_owner, self.index)}
        add_abilities = [p for p in option_ability_profiles(variant, self.index)
                         if p["id"] not in default_ab_ids]

        if not add_profs and not add_abilities:
            return  # nothing distinctive

        name = ", ".join(
            [split_name_rule_suffix(p.get("name", ""))[0] for p in add_profs]
            + [p.get("name", "") for p in add_abilities])
        self._emit_weapon_option(variant, add_profs, remove_profs, unit_id, profile_id,
                                 single_profile, name=name, add_abilities=add_abilities)

    def _emit_weapon_option(self, source, add_profs, remove_profs, unit_id, profile_id,
                            single_profile, name=None, add_abilities=None):
        add_ids = []
        for p in add_profs:
            eid = self.add_weapon(p)
            if eid not in add_ids:
                add_ids.append(eid)
        for p in add_abilities or []:
            rid, _value = self.add_ability_rule(p)
            if rid not in add_ids:
                add_ids.append(rid)
        if not add_ids:
            return
        remove_ids = []
        for p in remove_profs:
            eid = self.add_weapon(p)
            if eid not in remove_ids:
                remove_ids.append(eid)

        name = name if name is not None else source.get("name", "")
        opt_type = 1 if single_profile else 4  # ModifyItemOnAll vs ModifyItemOnSingle
        option_id = self._reuse_id("options", name, opt_type, "options_" + source["id"])
        option_id = self._dedup_content("options", (name, opt_type, tuple(add_ids)), option_id)
        if option_id not in self.options:
            self.options[option_id] = {
                "Id": option_id,
                "Name": name,
                "Type": opt_type,
                "ItemsToAdd": [{"Id": i} for i in add_ids],
            }

        remove_refs = [{"Id": i} for i in remove_ids]
        if single_profile:
            key = ("u", option_id, unit_id, tuple(remove_ids))
            if key in self._modrec_seen:
                return
            self._modrec_seen.add(key)
            rec = {"OptionId": option_id, "UnitId": unit_id}
            if remove_refs:
                rec["ReferencedItemsToRemove"] = remove_refs
            self.modified_units.append(rec)
        else:
            key = ("p", option_id, profile_id, tuple(remove_ids))
            if key in self._modrec_seen:
                return
            self._modrec_seen.add(key)
            rec = {"OptionId": option_id, "ProfileId": profile_id}
            if remove_refs:
                rec["ReferencedItemsToRemove"] = remove_refs
            self.modified_profiles.append(rec)

    # -- unit --------------------------------------------------------------
    def convert_unit(self, unit):
        keywords = []
        primary_role = None
        for link in unit.get("categoryLinks", []) or []:
            cname = link.get("name", "")
            if not cname:
                continue
            display = cname.split(":", 1)[-1].strip() if cname.startswith("Faction:") else cname
            up = display.upper()
            if up not in keywords:
                keywords.append(up)
            if link.get("primary") and primary_role is None:
                primary_role = display

        # Collect unit-level abilities and rules
        unit_abilities = []
        for p, info, included in ability_profiles_of(unit, self.index):
            if p.get("typeName") in ABILITY_TYPES:
                rid, value = self.add_ability_rule(p)
            elif p.get("description"):  # It's a rule object
                rid, value = self.add_rule(p)
            else:
                continue
            unit_abilities.append((rid, info or value, included))

        models = find_models(unit)
        pairs = []
        variant_weapons = []  # weapons from non-default siblings, catalogued but unlinked
        for default, others in models:
            # Some roles (e.g. Flash Gitz's Kaptin) carry no profile of their own and
            # rely on the enclosing unit's own top-level Unit profile for stats.
            prof = unit_profile_of(default, self.index) or unit_profile_of(unit, self.index)
            if prof:
                pairs.append((default, prof, others))
            for other in others:
                variant_weapons.extend(wp for wp, _ in weapon_profiles_of(other, self.index))
        if not pairs:
            prof = unit_profile_of(unit, self.index)
            if prof:
                pairs.append((unit, prof, []))

        # The first BasicProfileId is the unit's "main" profile in WDS; order roles by
        # descending squad-slot quota so the bulk troopers (highest max) lead, then
        # leaders/specialists (e.g. Boyz -> Boy before Nob). Stable for equal quotas.
        pairs.sort(key=lambda p: -model_max_constraint(p[0]))

        unit_id = self._reuse_id("units", unit.get("name", ""), "Unit", "unit_" + unit["id"])
        # Type 1/modifiedunit only for a genuine lone-model unit: exactly one profile
        # AND that model has no squad-slot quota. A squad that happens to collapse to
        # one shared profile (e.g. Deffkoptas, Nobz, Mek Gunz - multiple physical models,
        # some with a weapon swap) still needs per-model Type 4/modifiedprofile options.
        single_profile = len(pairs) == 1 and model_max_constraint(pairs[0][0]) <= 1

        basic_profile_ids = []
        for owner, prof, others in pairs:
            profile_name = model_base_name(owner.get("name", prof.get("name", "")))
            # Fallback candidate keyed by the model's own id, not the (possibly shared -
            # e.g. many units' 'Nob' all link to one BattleScribe profile) stat source;
            # content dedup below decides if two profiles truly are the same.
            candidate_profile_id = self._reuse_id("profiles", profile_name, "Profile", "profile_" + owner["id"])
            statline_attrs = make_statline(prof, UNIT_STAT_KEYS)
            statline_id = self._reuse_id("statlines", prof.get("name", ""), "Statline", "statline_" + prof["id"])
            statline_id = self._dedup_content(
                "statlines", (prof.get("name", ""), tuple(sorted(statline_attrs.items()))), statline_id)
            if statline_id not in self.statlines:
                self.statlines[statline_id] = {
                    "Id": statline_id,
                    "Name": prof.get("name", ""),
                    "Type": "Statline",
                    "Attributes": statline_attrs,
                }
            children = [{"Id": statline_id}]
            seen_rule_names = set()

            def add_rule_ref(rid, info):
                # Origin sometimes defines two distinct rules sharing one display
                # name (e.g. a model-specific "Support" ability + the generic
                # "Support" mechanic rule); only the first is kept per profile.
                name = self.rules.get(rid, {}).get("Name")
                if name is not None:
                    if name in seen_rule_names:
                        return
                    seen_rule_names.add(name)
                ref = {"Id": rid}
                if info:
                    ref["Info"] = info
                children.append(ref)

            for rid, info, included in unit_abilities:
                if not included:
                    continue
                add_rule_ref(rid, info)
            if owner is not unit:
                for p, info, included in ability_profiles_of(owner, self.index):
                    if p.get("typeName") in ABILITY_TYPES:
                        rid, value = self.add_ability_rule(p)
                    elif p.get("description"):
                        rid, value = self.add_rule(p)
                    else:
                        continue
                    if not included:
                        continue
                    add_rule_ref(rid, info or value)
            for wp, mandatory in weapon_profiles_of(owner, self.index):
                equip_id = self.add_weapon(wp)  # always catalogue the equipment, even if optional
                if mandatory:
                    children.append({"Id": equip_id})

            children_fp = tuple((c["Id"], c.get("Info")) for c in children)
            profile_id = self._dedup_content("profiles", (profile_name, children_fp), candidate_profile_id)
            if profile_id not in self.profiles:
                self.profiles[profile_id] = {
                    "Id": profile_id,
                    "Name": profile_name,
                    "Type": "Profile",
                    "Children": children,
                    "BaseId": "",
                }
            if profile_id not in basic_profile_ids:
                basic_profile_ids.append(profile_id)

            self.collect_weapon_options(owner, unit_id, profile_id, single_profile)
            for variant in others:
                self.emit_variant_option(variant, owner, unit_id, profile_id, single_profile)

        for wp in variant_weapons:
            self.add_weapon(wp)  # pre-catalogue excluded model variants' weapons, unlinked

        attributes = {}
        if keywords:
            attributes["Keywords"] = ", ".join(keywords)
        self.units.append({
            "Id": unit_id,
            "Name": unit.get("name", ""),
            "Type": "Unit",
            "Attributes": attributes,
            "BasicProfileIds": basic_profile_ids,
            "DefaultFront": 10 if "INFANTRY" in keywords else 1,
            "Formation": 3,
        })
        role = primary_role or "Other"
        self.hierarchy.setdefault(role, []).append(unit_id)


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_json(path, data):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def update_manifest(new_rel_files):
    path = os.path.join(WDS_DIR, "manifest.json")
    with open(path, "r", encoding="utf-8") as fh:
        manifest = json.load(fh)
    manifest["version"] = int(manifest.get("version", 0)) + 1
    files = manifest.setdefault("files", [])
    for rel in new_rel_files:
        if rel not in files:
            files.append(rel)
    write_json(path, manifest)
    return manifest["version"]


def update_hierarchy(faction, role_map):
    path = os.path.join(WDS_DIR, "hierarchy.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            hierarchy = json.load(fh)
    else:
        hierarchy = {}
    hierarchy.setdefault("Factions", {})[faction] = role_map
    write_json(path, hierarchy)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(description="BattleScribe -> WDS converter")
    parser.add_argument("faction", nargs="?", default="Orks",
                        help="Faction name (default: Orks)")
    args = parser.parse_args(argv)

    if not os.path.isdir(ORIGIN_DIR):
        sys.exit(f"Origin folder not found: {ORIGIN_DIR}")

    catalogues = load_catalogues(ORIGIN_DIR)
    index, rule_text, known_bases = build_index(catalogues)
    faction, catalogue = resolve_faction(catalogues, args.faction)
    if catalogue is None:
        sys.exit(f"Faction '{args.faction}' not found in {ORIGIN_DIR}")

    out_dir = os.path.join(WDS_DIR, faction)
    os.makedirs(out_dir, exist_ok=True)

    # Reuse Ids already assigned to same (Name, Type) entries in the destination.
    existing = load_existing_ids(out_dir)
    converter = Converter(index, rule_text, existing, known_bases)
    for unit in find_units(catalogue, index):
        converter.convert_unit(unit)

    outputs = {
        "units.json": converter.units,
        "profiles.json": list(converter.profiles.values()),
        "statlines.json": list(converter.statlines.values()),
        "equipment.json": list(converter.equipment.values()),
        "rules.json": list(converter.rules.values()),
        "options.json": list(converter.options.values()),
        "modifiedunit.json": converter.modified_units,
        "modifiedprofile.json": converter.modified_profiles,
    }
    for filename, data in outputs.items():
        write_json(os.path.join(out_dir, filename), data)

    new_rel_files = [f"{faction}/{name}" for name in outputs]
    version = update_manifest(new_rel_files)
    update_hierarchy(faction, converter.hierarchy)

    print(f"Converted faction: {faction}")
    print(f"  units:     {len(converter.units)}")
    print(f"  profiles:  {len(converter.profiles)}")
    print(f"  statlines: {len(converter.statlines)}")
    print(f"  equipment: {len(converter.equipment)}")
    print(f"  rules:     {len(converter.rules)}")
    print(f"  options:   {len(converter.options)}")
    print(f"  modifiedunit:    {len(converter.modified_units)}")
    print(f"  modifiedprofile: {len(converter.modified_profiles)}")
    print(f"  output:    {out_dir}")
    print(f"  manifest version -> {version}")


if __name__ == "__main__":
    main()
