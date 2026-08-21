from __future__ import annotations

import os
import re

import httpx


class RepositoryDiscovery:
    async def find_official_repo(self, title: str) -> str | None:
        query = re.sub(r"[^\w\s-]", " ", title)[:180].strip()
        headers = {"Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "Replicator/0.1"}
        if token := os.getenv("GITHUB_TOKEN"):
            headers["Authorization"] = f"Bearer {token}"
        async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
            response = await client.get("https://api.github.com/search/repositories",
                params={"q": f'"{query}" in:name,description,readme', "sort": "stars", "per_page": 5},
                headers=headers)
        if response.status_code in {403, 429}:
            return None
        response.raise_for_status()
        for item in response.json().get("items", []):
            url = item.get("html_url", "")
            if re.fullmatch(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", url):
                return url
        return None
