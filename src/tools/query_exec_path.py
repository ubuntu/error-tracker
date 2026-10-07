import sys
from argparse import ArgumentParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from errors import cassie
from errortracker import cassandra
from errortracker.cassandra_schema import OOPS, DayOOPS


def parse_args():
    parser = ArgumentParser(
        description="A tool to search the Error Tracker for a particular substring in the ExecutablePath"
    )
    parser.add_argument(
        "--start-x-days-ago",
        type=int,
        default=0,
        help="How many days back should the search start (default: 0)",
    )
    parser.add_argument(
        "--end-x-days-ago",
        type=int,
        default=10,
        help="How many days back should the search end (default: 10)",
    )
    parser.add_argument(
        "exec_path_substring",
        help="The string to look for in ExecutablePath. The search goes backward in time, yielding older and older results.",
    )
    args = parser.parse_args()
    if args.start_x_days_ago > args.end_x_days_ago:
        parser.error(
            "--start-x-days-ago should be lower than --end-x-days-ago (search goes backward)"
        )
    return args


def main():
    args = parse_args()

    cassandra.setup_cassandra()

    stop = False
    dates = cassie._get_range_of_dates(args.start_x_days_ago, args.end_x_days_ago)
    print(f"Searching for {args.exec_path_substring}")
    print(f"Dates: {dates}")
    total_count = 0
    for date in dates:
        print("=" * 80)
        print("Querying day", date)
        day_count = 0
        for _oops in DayOOPS.objects.filter(key=date.encode()).limit(None).all():
            oops_id = _oops.value
            try:
                oops = OOPS.get_as_dict(key=oops_id)
                if "ExecutablePath" in oops and args.exec_path_substring in oops["ExecutablePath"]:
                    print("-" * 80)
                    print(
                        f"https://errors.ubuntu.com/oops/{oops_id.decode()} - {oops['ExecutablePath']}"
                    )
                    sas = oops.get("StacktraceAddressSignature", "")
                    if sas:
                        print(f"    StacktraceAddressSignature: {sas}")
                    else:
                        print("    No StacktraceAddressSignature")
                    day_count += 1
            except KeyboardInterrupt:
                print("Stopping here upon user request")
                stop = True
            except Exception as e:
                print("Issue when querying OOPS:", e, file=sys.stderr)
            if stop:
                break
        print("-" * 80)
        print(f"Found {day_count} crashes for {date}")
        total_count += day_count
        if stop:
            break
    print("=" * 80)
    print(f"Found {total_count} crashes in total")


if __name__ == "__main__":
    main()
