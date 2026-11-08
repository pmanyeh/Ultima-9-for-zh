"""P8-A terminology candidates for the authority file (U9_TERMS.csv).

Adapted from the Ultima VIII project's ``u8catalog.py terms``: proper names are
collected from the game text, hand-edited fields are kept, counts and examples are
refreshed. The committed CSV holds terms, counts and entry locations only. Example
sentences go to a separate LOCAL ONLY review file.
"""
import collections
import csv
import io
import re

from .glossary import CATEGORIES, COLUMNS, annotation_mode

# Words capitalised for reasons other than being a name (sentence openers, pronouns,
# archaic forms). Taken from the U8 list, plus forms seen in Ultima IX dialogue.
COMMON_WORDS = set("""I A An The And But Or Nor So Yet For If Then Than When While Where Why How What Who Whom
Whose Which This That These Those There Here It Its He She We You They Me Him Her Us Them My Your His Our Their
Aye Nay Yes No Not Oh Ah Well Now Perhaps Indeed Alas Hail Farewell Greetings Hello Goodbye Good Thank Thanks
Please Sorry Come Go Let Do Does Did Is Are Was Were Be Been Am Have Has Had Will Would Shall Should Can Could
May Might Must Ye Thee Thou Thy Thine Tis Twas Mr Sir Lady Lord Mine Some Any All None One Two Three Each
Every Many Much More Most Only Even Just Also Still Again Once After Before Since Until Unless Though Although
With Without Within Into Onto Upon From To In On At By Of Off Out Over Under About Above Below Between Through
Hey Hmm Ha Bah Ugh Eh Huh Don't I'm I'll I've I'd It's That's What's There's You're You'll Let's
Okay OK Ahh Hmmm Mmm Uh Um Er Wait Look Listen See Take Give Tell Ask Find Bring Keep Never Always Very
Why Whatever However Therefore Besides Certainly Surely Truly Really Maybe Excuse Pardon Welcome""".split())
TITLE_PREFIXES = {"Lord", "Lady", "Sir", "King", "Queen", "Captain", "Master", "Mistress", "Brother", "Sister"}
VIRTUES = {"Honesty", "Compassion", "Valor", "Justice", "Sacrifice", "Honor", "Spirituality", "Humility",
           "Truth", "Love", "Courage"}
PLACE_WORDS = {"Shrine", "Castle", "Dungeon", "Temple", "Tower", "Isle", "Island", "Lake", "Mount",
               "Mountain", "Forest", "Keep", "Abbey", "Lighthouse", "Cove", "Valley", "Sea", "Bay", "Inn",
               "Tavern", "Column", "Hythloth", "Despise", "Deceit", "Destard", "Wrong", "Covetous", "Shame"}
# Ultima VIII "proposed" entries are carried over only for names, not for common words.
U8_NAME_CATEGORIES = {"person", "place", "faction", "creature", "title"}
U8_CATEGORY = {"person": "person", "place": "place", "item": "item", "spell": "spell", "creature": "monster",
               "title": "title", "faction": "organization", "other": "other"}
NAME = re.compile(r"\b([A-Z][a-z][A-Za-z']*(?:(?: of(?: the)?| the)? [A-Z][a-z][A-Za-z']*)*)")
SENTENCE = re.compile(r"(?<=[.!?:;*])\s+|\.\.\.\s*|\r?\n")
SECTION = re.compile(r"\\ConvoLib\\(?P<region>[^\\]+)\\(?P<file>[^\\.: ]+)")
REVIEW_COLUMNS = ("source", "category", "status", "target", "annotate", "count", "example", "context", "u8",
                  "sample")


def _clean(text):
    return text.replace("\x92", "'").replace("’", "'")


def names_in(text):
    """Capitalised names that do not open a sentence."""
    for sentence in SENTENCE.split(_clean(text)):
        sentence = sentence.strip(" \t\"'(*-")
        for m in NAME.finditer(sentence):
            words = m.group(1).split()
            if m.start() == 0 and not (words[0] in TITLE_PREFIXES and len(words) > 1):
                # The opening word is capitalised anyway: "Hail Avatar" still names the Avatar.
                words = words[1:]
                while words and words[0] in ("of", "the"):
                    words = words[1:]
                if not words:
                    continue
            if words[0] in TITLE_PREFIXES and len(words) > 1:
                term = " ".join(words)
            else:
                while words and words[0] in COMMON_WORDS:
                    words = words[1:]
                if not words or not words[0][:1].isupper():
                    continue
                if words[-1] in ("of", "the"):
                    words = words[:-1]
                term = " ".join(words)
            term = re.sub(r"'s?$", "", term)
            if term and term not in COMMON_WORDS and all(w in ("of", "the") or w[:1].isupper() for w in term.split()):
                yield term


def text_sections(units):
    """entry id -> 'Region/File' from the source-file marker entries of text.flx."""
    current, out = None, {}
    for entry_id in sorted(units):
        unit = units[entry_id]
        if unit.text and not unit.editable:
            m = SECTION.search(unit.text)
            current = f"{m['region']}/{m['file']}" if m else None
        out[entry_id] = current
    return out


def guess_category(term, places, people):
    words = term.split()
    if term in VIRTUES:
        return "virtue"
    if term in places or any(w in PLACE_WORDS for w in words):
        return "place"
    if words[0] in TITLE_PREFIXES or term in people:
        return "person"
    return "other"


def collect(text_units, typename_units, book_units, minimum=3):
    """{term: {"category", "count", "example", "context", "sample"}}; deterministic."""
    sections = text_sections(text_units)
    places = {s.split("/")[0] for s in sections.values() if s}
    people = {s.split("/")[1] for s in sections.values() if s}
    counts, examples = collections.Counter(), {}
    order = []
    for entry_id in sorted(text_units):
        u = text_units[entry_id]
        if u.editable and u.text:
            order.append((f"text.flx:{entry_id}", sections.get(entry_id) or "", u.text))
    for entry_id in sorted(book_units):
        u = book_units[entry_id]
        if u.editable and u.text:
            order.append((f"BOOKS-EN.FLX:{entry_id}", "book", u.text))
    for key, context, text in order:
        for term in names_in(text):
            counts[term] += 1
            if term not in examples:
                examples[term] = (key, context, text)
    found = {}
    for term, n in counts.items():
        if n >= minimum or term in places or term in people:
            key, context, text = examples[term]
            found[term] = {"category": guess_category(term, places, people), "count": n,
                           "example": key, "context": context, "sample": text}
    labels = collections.defaultdict(list)
    for entry_id in sorted(typename_units):
        u = typename_units[entry_id]
        if u.editable and u.text and u.text.strip():
            labels[u.text.strip()].append(entry_id)
    # An object name in dialogue ("Copper Necklace") ends like at least two examine labels.
    heads = collections.Counter(label.split()[-1].casefold() for label in labels)
    for term, entry in found.items():
        if entry["category"] == "other" and heads[term.split()[-1].casefold()] >= 2:
            entry["category"] = "item"
    for label, ids in labels.items():
        entry = found.get(label)
        if entry:
            entry["count"] += len(ids)
            if entry["category"] == "other":
                entry["category"] = "item"
        else:
            found[label] = {"category": "item", "count": len(ids), "example": f"TYPENAME.FLX:{ids[0]}",
                            "context": "examine label", "sample": label}
    return found


def load_u8_authority(data):
    """Rows of the Ultima VIII authority.tsv -> {english: row}."""
    out = {}
    lines = [line for line in data.decode("utf-8").splitlines() if line and not line.startswith("#")]
    if not lines:
        return out
    header = lines[0].split("\t")
    for line in lines[1:]:
        row = dict(zip(header, line.split("\t")))
        if row.get("english"):
            out[row["english"]] = row
    return out


def _u8_match(term, u8):
    if term in u8:
        return u8[term]
    folded = {k.casefold(): v for k, v in u8.items()}
    return folded.get(term.casefold())


def merge(old_rows, collected, u8=None):
    """Hand-edited fields win; counts and examples are refreshed; U8 fills undecided terms."""
    u8 = u8 or {}
    old = {r["source"]: r for r in old_rows}
    rows = []
    for source in sorted(set(old) | set(collected), key=lambda s: (s.casefold(), s)):
        o, c = old.get(source), collected.get(source)
        row = {k: "" for k in COLUMNS}
        row["source"] = source
        if o:
            row.update({k: o[k] for k in COLUMNS})
        else:
            row.update({"category": c["category"], "status": "todo", "enforcement": "recommended",
                        "reference": "P8-A candidate scan"})
        row["count"] = str(c["count"]) if c else "0"
        row["example"] = c["example"] if c else (o["example"] if o else "")
        match = _u8_match(source, u8)
        usable = match and (match.get("status") in ("approved", "keep") or
                            (match.get("status") == "proposed" and match.get("category") in U8_NAME_CATEGORIES))
        if usable:
            u8_target = match.get("translation") or (source if match["status"] == "keep" else "")
            note = f"U8 {match['status']}: {u8_target}"
            if row["status"] == "todo" and not row["target"] and u8_target:
                row["target"], row["status"] = u8_target, "proposed"
                row["reference"] = f"U8 authority.tsv ({match['status']})"
                if not o and row["category"] == "other" and match.get("category") in U8_CATEGORY:
                    row["category"] = U8_CATEGORY[match["category"]]
            elif row["target"] and u8_target and row["target"] != u8_target and note not in row["notes"]:
                row["notes"] = "; ".join(x for x in (row["notes"], note) if x)
        rows.append(row)
    # Chinese has no plural: "Gargoyles" proposes the target of "Gargoyle".
    by_source = {r["source"]: r for r in rows}
    for row in rows:
        if row["status"] != "todo" or row["target"] or not row["source"].endswith("s"):
            continue
        for singular in (row["source"][:-1], row["source"][:-2] if row["source"].endswith("es") else None):
            base = by_source.get(singular) if singular else None
            if base and base["target"] and base["status"] in ("proposed", "approved", "keep"):
                row["target"], row["status"] = base["target"], "proposed"
                row["reference"] = f"plural of {singular}"
                if row["category"] == "other":
                    row["category"] = base["category"]
                break
    rank = {c: i for i, c in enumerate(CATEGORIES)}
    rows.sort(key=lambda r: (rank.get(r["category"], len(rank)), r["source"].casefold(), r["source"]))
    return rows


def render_csv(rows):
    out = io.StringIO(newline="")
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(COLUMNS)
    for row in rows:
        writer.writerow([row[k] for k in COLUMNS])
    return out.getvalue().encode("utf-8")


def render_review(rows, collected, u8=None):
    """LOCAL ONLY: adds one source sentence per term for human review. Never commit."""
    u8 = u8 or {}
    out = io.StringIO(newline="")
    writer = csv.writer(out, delimiter="\t", lineterminator="\n")
    writer.writerow(REVIEW_COLUMNS)
    for row in rows:
        c = collected.get(row["source"], {})
        match = _u8_match(row["source"], u8)
        u8_text = f"{match.get('status')}: {match.get('translation') or ''}" if match else ""
        sample = " ".join(c.get("sample", "").split())[:200]
        writer.writerow([row["source"], row["category"], row["status"], row["target"], annotation_mode(row),
                         row["count"], row["example"], c.get("context", ""), u8_text, sample])
    return out.getvalue().encode("utf-8")


def summary(rows):
    by_category = collections.Counter(r["category"] for r in rows)
    by_status = collections.Counter(r["status"] for r in rows)
    return {"terms": len(rows), "by_category": dict(sorted(by_category.items())),
            "by_status": dict(sorted(by_status.items()))}
