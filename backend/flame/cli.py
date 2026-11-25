"""Operator CLI for Flame Loop v0.1.  Run from backend/:  python -m flame.cli --help"""
import argparse
import json
import sys

from . import render, service
from .config import db_path
from .errors import FlameError


def _out(args, data, text):
    print(json.dumps(data, indent=2, sort_keys=True) if getattr(args, "json", False) else text)


def _parser():
    p = argparse.ArgumentParser(prog="python -m flame.cli", description="Flame Loop v0.1 operator CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="apply schema migrations")
    sub.add_parser("missions", help="list all missions")

    c = sub.add_parser("create", help="create a draft mission")
    c.add_argument("id")
    c.add_argument("--title", required=True)
    c.add_argument("--goal", required=True)
    c.add_argument("--success", default="", help="how success is judged, in words")
    c.add_argument("--target-proofs", type=int, default=None)
    c.add_argument("--owner", default="")
    c.add_argument("--next-move", default="")

    s = sub.add_parser("set", help="edit a draft or active mission")
    s.add_argument("id")
    s.add_argument("--title")
    s.add_argument("--goal")
    s.add_argument("--success")
    s.add_argument("--target-proofs", type=int)
    s.add_argument("--owner")
    s.add_argument("--next-move")
    s.add_argument("--blocker", help="add a blocker")
    s.add_argument("--clear-blockers", action="store_true")

    a = sub.add_parser("activate", help="make a draft the active mission")
    a.add_argument("id")
    k = sub.add_parser("close", help="close the active mission (stops linking new proofs)")
    k.add_argument("id")

    st = sub.add_parser("status", help="show mission state (default: the active mission)")
    st.add_argument("id", nargs="?")
    st.add_argument("--json", action="store_true")

    pr = sub.add_parser("proofs", help="list proofs recorded for a mission")
    pr.add_argument("id", nargs="?", help="mission id; omit for the active mission; 'none' for unlinked")
    pr.add_argument("--json", action="store_true")

    v = sub.add_parser("verify", help="mark a proof verified/rejected after checking it on-chain")
    v.add_argument("proof_id", type=int)
    v.add_argument("status", choices=["verified", "rejected", "unverified"])

    o = sub.add_parser("outcome", help="generate (or show) the outcome and draft next mission")
    o.add_argument("id")
    o.add_argument("--json", action="store_true")
    return p


def _fmt_mission(m):
    target = m["target_proofs"] or "-"
    return f"{m['id']}  {m['status']:<7}  target={target}  {m['title']}"


def run(args) -> int:
    if args.cmd == "init":
        print(f"schema version {service.init()} at {db_path()}")
    elif args.cmd == "missions":
        service.init()
        for m in service.list_missions():
            print(_fmt_mission(m))
    elif args.cmd == "create":
        service.init()
        m = service.create_mission(args.id, args.title, args.goal, args.success, args.target_proofs,
                                   args.owner, args.next_move)
        print(f"created {_fmt_mission(m)}")
    elif args.cmd == "set":
        service.init()
        m = service.update_mission(args.id, title=args.title, goal=args.goal, success_measure=args.success,
                                   target_proofs=args.target_proofs, owner=args.owner, next_move=args.next_move,
                                   add_blocker=args.blocker, clear_blockers=args.clear_blockers)
        print(f"updated {_fmt_mission(m)}")
    elif args.cmd == "activate":
        service.init()
        print(f"activated {_fmt_mission(service.activate_mission(args.id))}")
    elif args.cmd == "close":
        service.init()
        print(f"closed {_fmt_mission(service.close_mission(args.id))}")
        print(f"next: python -m flame.cli outcome {args.id}")
    elif args.cmd == "status":
        service.init()
        snap = service.snapshot(args.id)
        _out(args, snap, render.render_status(snap, "en", admin=True))
    elif args.cmd == "proofs":
        service.init()
        mid = args.id
        if mid is None:
            active = service.active_mission()
            mid = active["id"] if active else None
        elif mid.lower() == "none":
            mid = None
        rows = service.list_proofs(mid)
        if getattr(args, "json", False):
            print(json.dumps(rows, indent=2))
        else:
            for r in rows:
                print(f"#{r['id']}  {r['created_at']}  {r['blessing']:<8} {r['verification_status']:<10} "
                      f"{r['delivery_status']:<9} who={r['participant']}  {r['proof_hash']}")
            print(f"{len(rows)} proofs")
    elif args.cmd == "verify":
        service.init()
        service.verify_proof(args.proof_id, args.status)
        print(f"proof {args.proof_id} marked {args.status}")
    elif args.cmd == "outcome":
        service.init()
        out = service.generate_outcome(args.id)
        mission = service.get_mission(args.id)
        nxt = service.get_mission(out["next_mission_id"]) if out["next_mission_id"] else None
        _out(args, out, render.render_outcome(out, mission, nxt))
    return 0


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    try:
        return run(args)
    except FlameError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
