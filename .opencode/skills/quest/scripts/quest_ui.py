#!/usr/bin/env python3
"""Parse a uiautomator XML dump for the quest CLI.

Two modes:
  elements <dump.xml> [--pkg P] [--all]   -> JSON array of nodes
  find     <dump.xml> [selectors]         -> JSON {count, node}

Selectors: --text T --id I --desc D --pkg P --exact --index N
Exit 0 on a unique match, 1 when nothing matches, 2 on an ambiguous match.
"""

import json
import re
import sys
import xml.etree.ElementTree as ET


def parse_nodes(path):
    try:
        root = ET.parse(path).getroot()
    except Exception as exc:  # noqa: BLE001 - surface the parse error to the CLI
        print(f"quest: could not parse {path}: {exc}", file=sys.stderr)
        sys.exit(3)

    nodes = []
    for element in root.iter("node"):
        attrs = element.attrib
        match = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", attrs.get("bounds", ""))
        if not match:
            continue
        x1, y1, x2, y2 = map(int, match.groups())
        nodes.append(
            {
                "label": attrs.get("text") or attrs.get("content-desc") or "",
                "text": attrs.get("text", ""),
                "desc": attrs.get("content-desc", ""),
                "bounds": [[x1, y1], [x2, y2]],
                "center": [(x1 + x2) // 2, (y1 + y2) // 2],
                "clickable": attrs.get("clickable") == "true",
                "resource-id": attrs.get("resource-id", ""),
                "class": attrs.get("class", ""),
                "package": attrs.get("package", ""),
            }
        )
    return nodes


def parse_flags(argv):
    flags = {}
    index = 0
    while index < len(argv):
        if argv[index].startswith("--"):
            key = argv[index][2:]
            if key in ("exact", "gone"):
                flags[key] = True
            else:
                index += 1
                flags[key] = argv[index] if index < len(argv) else ""
        index += 1
    return flags


def has_selector(flags):
    return bool(flags.get("text") or flags.get("id") or flags.get("desc"))


def matches(node, flags):
    def equal(have, want):
        have_l = (have or "").lower()
        want_l = want.lower()
        return have_l == want_l if flags.get("exact") else want_l in have_l

    if flags.get("pkg") and node["package"] != flags["pkg"]:
        return False
    if flags.get("text") and not equal(node["text"], flags["text"]):
        return False
    if flags.get("desc") and not equal(node["desc"], flags["desc"]):
        return False
    if flags.get("id") and not equal(node["resource-id"].split(":id/")[-1], flags["id"]):
        return False
    return True


def main():
    if len(sys.argv) < 3:
        print("usage: quest_ui.py elements|find <dump.xml> [selectors]", file=sys.stderr)
        return 2

    mode, path = sys.argv[1], sys.argv[2]
    flags = parse_flags(sys.argv[3:])
    nodes = parse_nodes(path)

    if mode == "elements":
        if flags.get("pkg"):
            nodes = [node for node in nodes if node["package"] == flags["pkg"]]
        if not flags.get("all"):
            nodes = [
                node
                for node in nodes
                if node["label"] or node["resource-id"] or node["clickable"]
            ]
        print(json.dumps(nodes, ensure_ascii=False, indent=2))
        return 0

    if mode == "find":
        if not has_selector(flags):
            print("quest: need a selector: --text <t> | --id <id> | --desc <d>", file=sys.stderr)
            return 2
        hits = [node for node in nodes if matches(node, flags)]
        if not hits:
            print(json.dumps({"count": 0, "node": None}, ensure_ascii=False))
            print("quest: no element matches the selector", file=sys.stderr)
            return 1
        if len(hits) > 1 and "index" not in flags:
            print(json.dumps({"count": len(hits), "node": None}, ensure_ascii=False))
            print(f"quest: {len(hits)} elements match; add --index N or --exact:", file=sys.stderr)
            for position, hit in enumerate(hits):
                print(
                    f'  [{position}] "{hit["label"]}" {hit["resource-id"]} @{hit["center"]}',
                    file=sys.stderr,
                )
            return 2
        try:
            position = int(flags.get("index", 0) or 0)
        except ValueError:
            print("quest: --index must be an integer", file=sys.stderr)
            return 2
        if position < 0 or position >= len(hits):
            print(json.dumps({"count": len(hits), "node": None}, ensure_ascii=False))
            print(
                f"quest: --index {position} out of range (0..{len(hits) - 1})",
                file=sys.stderr,
            )
            return 2
        print(json.dumps({"count": len(hits), "node": hits[position]}, ensure_ascii=False, indent=2))
        return 0

    if mode == "exists":
        if not has_selector(flags):
            print("quest: need a selector: --text <t> | --id <id> | --desc <d>", file=sys.stderr)
            return 2
        hits = [node for node in nodes if matches(node, flags)]
        print(
            json.dumps(
                {"exists": bool(hits), "count": len(hits), "first": hits[0] if hits else None},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0 if hits else 1

    print(f"quest: unknown mode {mode}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
