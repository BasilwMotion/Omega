"""
Vercel Serverless Function: /api/tracker
Handles financial data processing and goal management.
Stateless — all state is passed in by the client.
"""

import json
from http.server import BaseHTTPRequestHandler
from datetime import datetime


def calculate_metrics(transactions: list) -> dict:
    """Compute gain, expense, net, and category breakdowns."""
    gains = 0.0
    expenses = 0.0
    categories: dict[str, float] = {}
    timeline: list[dict] = []
    running_net = 0.0

    for tx in sorted(transactions, key=lambda t: t.get("date", "")):
        amount = float(tx.get("amount", 0))
        category = tx.get("category", "Uncategorized")
        tx_type = tx.get("type", "expense").lower()
        date = tx.get("date", datetime.today().strftime("%Y-%m-%d"))

        if tx_type == "income":
            gains += amount
            running_net += amount
        else:
            expenses += amount
            running_net -= amount
            categories[category] = categories.get(category, 0) + amount

        timeline.append({
            "date": date,
            "gains": round(gains, 2),
            "expenses": round(expenses, 2),
            "net": round(running_net, 2),
        })

    return {
        "gains": round(gains, 2),
        "expenses": round(expenses, 2),
        "net": round(gains - expenses, 2),
        "categories": categories,
        "timeline": timeline,
    }


def calculate_staff_efficiency(staff: list) -> list:
    """Compute work-rate efficiency % per staff member."""
    result = []
    for member in staff:
        completed = int(member.get("tasks_completed", 0))
        assigned = int(member.get("tasks_assigned", 1))
        efficiency = round((completed / assigned) * 100, 1) if assigned > 0 else 0
        result.append({
            "name": member.get("name", "Unknown"),
            "role": member.get("role", "Team Member"),
            "tasks_completed": completed,
            "tasks_assigned": assigned,
            "efficiency": efficiency,
            "milestones": member.get("milestones", []),
        })
    return result


def goal_analysis(goals: list, transactions: list) -> list:
    """Compare each savings goal against current net position."""
    metrics = calculate_metrics(transactions)
    net = metrics["net"]
    analyzed = []
    for goal in goals:
        target = float(goal.get("target", 0))
        progress = min(round((net / target) * 100, 1), 100) if target > 0 else 0
        analyzed.append({
            "name": goal.get("name", "Goal"),
            "target": target,
            "current": round(net, 2),
            "progress": progress,
            "status": "achieved" if progress >= 100 else "in_progress",
        })
    return analyzed


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self._set_cors()
        self.end_headers()

    def do_GET(self):
        payload = {
            "status": "Omega Financial Tracker API",
            "version": "1.0.0",
            "endpoints": {
                "POST /api/tracker": "Process transactions, staff, and goals"
            }
        }
        self._respond(200, payload)

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length)
            body = json.loads(raw.decode("utf-8"))

            transactions = body.get("transactions", [])
            staff = body.get("staff", [])
            goals = body.get("goals", [])

            metrics = calculate_metrics(transactions)
            staff_data = calculate_staff_efficiency(staff)
            goal_data = goal_analysis(goals, transactions)

            self._respond(200, {
                "metrics": metrics,
                "staff": staff_data,
                "goals": goal_data,
            })
        except json.JSONDecodeError:
            self._respond(400, {"error": "Invalid JSON body"})
        except Exception as e:
            self._respond(500, {"error": str(e)})

    def _set_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _respond(self, code: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self._set_cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass  # suppress default server logs
