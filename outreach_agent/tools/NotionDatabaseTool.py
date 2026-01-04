import json
import os
from typing import Literal, Optional

import requests
from agency_swarm.tools import BaseTool
from pydantic import Field
from dotenv import load_dotenv

load_dotenv()


class NotionDatabaseTool(BaseTool):
    """
    Perform Notion database operations with a confirmed database id. Supports listing databases, listing/querying pages,
    fetching a page, and creating/updating pages. Uses a cached context key 'lead_db_id' when target_id is omitted.
    """

    operation: Literal[
        "list_databases",
        "list_database_pages",
        "query_database",
        "fetch_page",
        "create_page",
        "update_page",
    ] = Field(..., description="Which Notion operation to perform.")
    target_id: Optional[str] = Field(
        None,
        description="Database id for list/query/create, or page id for fetch/update. If omitted, falls back to context key 'lead_db_id'.",
    )
    properties_json: Optional[str] = Field(
        None,
        description="JSON string of properties for create/update operations (e.g., {\"Name\": {\"title\": [{\"text\": {\"content\": \"Alice\"}}]}}).",
    )
    page_size: int = Field(10, description="Max items per page for list/query calls.")
    max_pages: int = Field(3, description="Max pages to paginate through for list/query calls.")

    def run(self) -> str:
        api_key = (
            os.getenv("NOTION_API_KEY")
            or os.getenv("NOTION_TOKEN")
            or os.getenv("NOTION_MCP_OAUTH_TOKEN")
            or os.getenv("NOTION_MCP_TOKEN")
        )
        if not api_key:
            raise ValueError("Missing Notion credentials: set NOTION_API_KEY (or NOTION_TOKEN / NOTION_MCP_OAUTH_TOKEN / NOTION_MCP_TOKEN).")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Notion-Version": os.getenv("NOTION_API_VERSION", "2022-06-28"),
            "Content-Type": "application/json",
        }

        target = self.target_id or self._context.get("lead_db_id")

        if self.operation == "list_databases":
            payload: dict = {"page_size": self.page_size, "filter": {"value": "database", "property": "object"}}
            results = []
            cursor = None
            for _ in range(self.max_pages):
                if cursor:
                    payload["start_cursor"] = cursor
                elif "start_cursor" in payload:
                    payload.pop("start_cursor")
                res = requests.post("https://api.notion.com/v1/search", headers=headers, json=payload, timeout=30)
                res.raise_for_status()
                data = res.json()
                results.extend(data.get("results", []))
                cursor = data.get("next_cursor")
                if not cursor:
                    break
            lines = [f"{idx}. {self._extract_title(db)} ({db.get('id')})" for idx, db in enumerate(results, 1)]
            return "Databases:\n" + ("\n".join(lines) if lines else "(none found)")

        if not target:
            raise ValueError("target_id is required (or set context lead_db_id) for this operation.")

        if self.operation == "list_database_pages":
            payload: dict = {"page_size": self.page_size}
            pages = []
            cursor = None
            for _ in range(self.max_pages):
                if cursor:
                    payload["start_cursor"] = cursor
                elif "start_cursor" in payload:
                    payload.pop("start_cursor")
                res = requests.post(
                    f"https://api.notion.com/v1/databases/{target}/query",
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
            lines = [f"{idx}. {self._extract_title(pg)} ({pg.get('id')})" for idx, pg in enumerate(pages, 1)]
            return f"Database {target} pages (paginated up to {self.max_pages} pages x {self.page_size}):\n" + (
                "\n".join(lines) if lines else "(none found)"
            )

        if self.operation == "query_database":
            payload: dict = {"page_size": self.page_size}
            res = requests.post(
                f"https://api.notion.com/v1/databases/{target}/query",
                headers=headers,
                json=payload,
                timeout=30,
            )
            res.raise_for_status()
            rows = res.json().get("results", [])
            body = "\n".join(f"- {self._extract_title(r)} ({r.get('id')})" for r in rows[:10])
            return f"Queried database {target}: {len(rows)} results (showing up to 10):\n{body}"

        if self.operation == "fetch_page":
            res = requests.get(f"https://api.notion.com/v1/pages/{target}", headers=headers, timeout=30)
            res.raise_for_status()
            data = res.json()
            return f"Fetched page {target} titled '{self._extract_title(data)}'."

        if self.operation == "create_page":
            if not self.properties_json:
                raise ValueError("properties_json is required for create_page.")
            properties = self._parse_json(self.properties_json, "properties_json")
            payload: dict = {"parent": {"database_id": target}, "properties": properties}
            res = requests.post("https://api.notion.com/v1/pages", headers=headers, json=payload, timeout=30)
            res.raise_for_status()
            created = res.json()
            return f"Created page in database {target} with id {created.get('id')}."

        if self.operation == "update_page":
            if not self.properties_json:
                raise ValueError("properties_json is required for update_page.")
            properties = self._parse_json(self.properties_json, "properties_json")
            res = requests.patch(
                f"https://api.notion.com/v1/pages/{target}",
                headers=headers,
                json={"properties": properties},
                timeout=30,
            )
            res.raise_for_status()
            return f"Updated page {target} properties."

        raise ValueError(f"Unsupported operation: {self.operation}")

    def _parse_json(self, raw: str, label: str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in {label}: {exc}") from exc

    @staticmethod
    def _extract_title(page_data: dict) -> str:
        props = page_data.get("properties", {})
        for prop in props.values():
            if isinstance(prop, dict) and prop.get("type") == "title":
                title_items = prop.get("title", [])
                if title_items:
                    return title_items[0].get("plain_text", "").strip() or "(untitled)"
        return "(untitled)"
