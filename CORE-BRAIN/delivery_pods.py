"""CORE-BRAIN delivery pods: round-robin revenue work across POD 1-3."""

import csv
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
HEADERS = ["timestamp", "pod_id", "role", "source_action", "deliverable", "status", "details"]


class DeliveryPod:
    """POD 1/2/3: Implementation Pod Lead, Automation Engineer, AI Specialist."""

    ROLES = ("Implementation Pod Lead", "Automation Engineer", "AI Specialist")

    def __init__(self, pod_id):
        self.pod_id = pod_id

    def record(self, role, row, slot):
        stamp = datetime.now().astimezone().isoformat(timespec="seconds")
        return dict(zip(HEADERS, (stamp, self.pod_id, role, row.get("action", ""),
                                  row.get("detail", ""), "ASSIGNED",
                                  f"round-robin slot {slot}/9 from revenue_leads.csv")))


class DeliveryOrchestrator:
    """Reads revenue_leads.csv and round-robins tasks across the three pods."""

    def run(self):
        with (BASE / "revenue_leads.csv").open(newline="", encoding="utf-8") as fh:
            tasks = list(csv.DictReader(fh))[::3][:9]
        pods = [DeliveryPod(f"POD {n}") for n in (1, 2, 3)]
        rows = []
        for slot, task in enumerate(tasks, 1):
            pod = pods[(slot - 1) % 3]
            role = DeliveryPod.ROLES[(slot - 1) // 3]
            rows.append(pod.record(role, task, slot))
        path = BASE / "pod_deliveries.csv"
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=HEADERS)
            writer.writeheader()
            writer.writerows(rows)
        return path, len(rows)


def main():
    path, count = DeliveryOrchestrator().run()
    print(f"wrote {path} ({count} records)")


if __name__ == "__main__":
    main()
