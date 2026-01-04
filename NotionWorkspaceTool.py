import json
import os
from typing import Literal, Optional

import requests
from agents import RunContextWrapper
from agents.tool import function_tool
from dotenv import load_dotenv

load_dotenv()


@function_tool(name_override="notion_workspace", strict_mode=True)
def notion_workspace(
    ctx: RunContextWrapper,
    operation: Literal[
        "query_database",
        "fetch_page",
        "update_page",
        "append_block",
        "list_databases",
        "list_database_pages",
        "create_page",
    ],
    target_id: str,
    properties_json: Optional[str] = None,
    rich_text: Optional[str] = None,
    page_size: int = 25,
    max_pages: int = 3,
) -> str:
    """
    Perform Notion workspace actions via the REST API: list databases, query a database, list pages in a database, fetch a page, update page properties, append a text block, or create a new page/record in a database.
    """

    api_key = (
        os.getenv("NOTION_API_KEY")
        or os.getenv("NOTION_TOKEN")
        or os.getenv("NOTION_MCP_OAUTH_TOKEN")
        or os.getenv("NOTION_MCP_TOKEN")
    )
    if not api_key:
        raise ValueError("Missing NOTION_API_KEY (or NOTION_TOKEN / NOTION_MCP_OAUTH_TOKEN / NOTION_MCP_TOKEN).")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Notion-Version": os.getenv("NOTION_API_VERSION", "2022-06-28"),
        "Content-Type": "application/json",
    }

    if operation == "list_databases":
        payload = {"page_size": page_size, "filter": {"value": "database", "property": "object"}}
        databases = []
        cursor = None
        for _ in range(max_pages):
            if cursor:
                payload["start_cursor"] = cursor
            elif "start_cursor" in payload:
                payload.pop("start_cursor")
            res = requests.post("https://api.notion.com/v1/search", headers=headers, json=payload, timeout=30)
            res.raise_for_status()
            data = res.json()
            databases.extend(data.get("results", []))
            cursor = data.get("next_cursor")
            if not cursor:
                break
        lines = []
        for idx, db in enumerate(databases, 1):
            lines.append(f"{idx}. { _extract_db_title(db) } ({db.get('id')})")
        return "Databases:\n" + ("\n".join(lines) if lines else "(none found)")

    if operation == "query_database":
        payload = {"page_size": page_size}
        res = requests.post(
            f"https://api.notion.com/v1/databases/{target_id}/query",
            headers=headers,
            json=payload,
            timeout=30,
        )
        res.raise_for_status()
        rows = res.json().get("results", [])
        titles = [_extract_title(r) for r in rows[:10]]
        body = "\n".join(f"- {t} ({r.get('id')})" for t, r in zip(titles, rows[:10]))
        return f"Queried database {target_id}: {len(rows)} results (showing up to 10):\n{body}"

    if operation == "list_database_pages":
        payload = {"page_size": page_size}
        pages = []
        cursor = None
        for _ in range(max_pages):
            if cursor:
                payload["start_cursor"] = cursor
            elif "start_cursor" in payload:
                payload.pop("start_cursor")
            res = requests.post(
                f"https://api.notion.com/v1/databases/{target_id}/query",
                headers=headers,
                json=payload,
                timeout=30,
            )
            res.raise_for_status()
            data = res.json()
            pages.extend(data.get("results", []))
            cursor = data.get("next_cursor")
            if not cursor:
                break
        lines = []
        for idx, pg in enumerate(pages, 1):
            lines.append(f"{idx}. {_extract_title(pg)} ({pg.get('id')})")
        return f"Database {target_id} pages (paginated up to {max_pages} pages x {page_size}):\n" + (
            "\n".join(lines) if lines else "(none found)"
        )

    if operation == "fetch_page":
        res = requests.get(
            f"https://api.notion.com/v1/pages/{target_id}",
            headers=headers,
            timeout=30,
        )
        res.raise_for_status()
        data = res.json()
        title = _extract_title(data)
        return f"Fetched page {target_id} titled '{title}'."

    if operation == "update_page":
        if not properties_json:
            raise ValueError("properties_json is required for update_page.")
        properties = json.loads(properties_json)
        res = requests.patch(
            f"https://api.notion.com/v1/pages/{target_id}",
            headers=headers,
            json={"properties": properties},
            timeout=30,
        )
        res.raise_for_status()
        return f"Updated page {target_id} properties."

    if operation == "append_block":
        if not rich_text:
            raise ValueError("rich_text is required for append_block.")
        payload = {
            "children": [
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": [{"type": "text", "text": {"content": rich_text}}]},
                }
            ]
        }
        res = requests.patch(
            f"https://api.notion.com/v1/blocks/{target_id}/children",
            headers=headers,
            json=payload,
            timeout=30,
        )
        res.raise_for_status()
        return f"Appended paragraph block under {target_id}."

    if operation == "create_page":
        if not properties_json:
            raise ValueError("properties_json is required for create_page.")
        properties = json.loads(properties_json)
        payload: dict = {"parent": {"database_id": target_id}, "properties": properties}
        if rich_text:
            payload["children"] = [
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": [{"type": "text", "text": {"content": rich_text}}]},
                }
            ]
        res = requests.post(
            "https://api.notion.com/v1/pages",
            headers=headers,
            json=payload,
            timeout=30,
        )
        res.raise_for_status()
        created = res.json()
        return f"Created page in database {target_id} with id {created.get('id')}."

    raise ValueError(f"Unsupported operation: {operation}")


def _extract_title(page_data: dict) -> str:
    props = page_data.get("properties", {})
    for prop in props.values():
        if isinstance(prop, dict) and prop.get("type") == "title":
            title_items = prop.get("title", [])
            if title_items:
                return title_items[0].get("plain_text", "").strip() or "(untitled)"
    return "(untitled)"


def _extract_db_title(db_data: dict) -> str:
    title_items = db_data.get("title", [])
    if title_items:
        return title_items[0].get("plain_text", "").strip() or "(untitled)"
    return "(untitled)"


if __name__ == "__main__":
    # Smoke test (will fail without valid env and IDs)
    try:
        print(
            notion_workspace(
                RunContextWrapper(context=None),
                operation="query_database",
                target_id="YOUR_DATABASE_ID",
                page_size=1,
            )
        )
    except Exception as exc:  # pragma: no cover - manual test
        print(f"Test failed: {exc}")
