"""Slack Socket Mode adapter. Slack user IDs are mapped to API actors locally."""

from uuid import uuid4

import httpx
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from envpilot.config import settings


API_URL = settings.envpilot_api_url.rstrip("/")


def api(method: str, path: str, user: str, **kwargs):
    with httpx.Client(timeout=10) as client:
        response = client.request(method, API_URL + path, headers={"X-Actor-Id": user, **kwargs.pop("headers", {})}, **kwargs)
    if response.is_error:
        detail = response.json().get("detail", {})
        code = detail.get("code", "request_failed") if isinstance(detail, dict) else "request_failed"
        raise ValueError(code)
    return response.json()


def build_app() -> App:
    app = App(token=settings.slack_bot_token)

    @app.command("/envpilot")
    def command(ack, body, respond, client):
        ack()
        user = body["user_id"]
        parts = body.get("text", "").strip().split()
        try:
            if len(parts) == 2 and parts[0] == "request":
                ttl = int(parts[1])
                env = api("POST", "/api/environments", user,
                          headers={"Idempotency-Key": body.get("trigger_id", str(uuid4()))},
                          json={"template_id": "ec2_sandbox", "template_version": "v1", "ttl_hours": ttl})
                respond(f"Request `{env['id']}` is pending approval.")
                for approver in filter(None, settings.envpilot_approver_ids.split(",")):
                    if approver != user:
                        client.chat_postMessage(channel=approver, text=f"Approve EnvPilot request {env['id']}?",
                                                blocks=[{"type": "section", "text": {"type": "mrkdwn", "text": f"<@{user}> requested a {ttl} hour sandbox (`{env['id']}`)."}},
                                                        {"type": "actions", "elements": [
                                                            {"type": "button", "text": {"type": "plain_text", "text": "Approve"}, "action_id": "envpilot_approve", "value": env["id"]},
                                                            {"type": "button", "text": {"type": "plain_text", "text": "Reject"}, "action_id": "envpilot_reject", "value": env["id"]}]}])
            elif len(parts) == 2 and parts[0] in {"status", "destroy"}:
                from uuid import UUID
                env_id = str(UUID(parts[1]))
                method = "GET" if parts[0] == "status" else "POST"
                path = f"/api/environments/{env_id}" + ("/destroy" if method == "POST" else "")
                env = api(method, path, user)
                respond(f"`{env_id}`: *{env['status']}*")
            elif parts == ["list"]:
                items = api("GET", "/api/environments", user)
                respond("\n".join(f"`{e['id']}`: {e['status']}" for e in items[:20]) or "No environments.")
            else:
                respond("Use `/envpilot request <hours>`, `/envpilot status <id>`, `/envpilot destroy <id>`, or `/envpilot list`.")
        except (ValueError, httpx.HTTPError) as exc:
            respond(f"EnvPilot request failed: {exc}")

    for action, endpoint in (("envpilot_approve", "approve"), ("envpilot_reject", "reject")):
        def handler(ack, body, respond, action, endpoint=endpoint):
            ack()
            try:
                env = api("POST", f"/api/environments/{action['value']}/{endpoint}", body["user"]["id"])
                respond(f"Environment `{env['id']}`: *{env['status']}*")
            except (ValueError, httpx.HTTPError) as exc:
                respond(f"Action failed: {exc}")
        app.action(action)(handler)
    return app


def main():
    if not settings.slack_bot_token or not settings.slack_app_token:
        raise RuntimeError("Set SLACK_BOT_TOKEN and SLACK_APP_TOKEN in the environment")
    SocketModeHandler(build_app(), settings.slack_app_token).start()


if __name__ == "__main__":
    main()
