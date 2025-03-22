#! /usr/bin/env python3
from functools import wraps
from typing import Any, Callable, TypeVar, cast

import asyncer
import typer
from rich.console import Console
from rich.table import Table

from shopify_client.client import ShopifyClient
from shopify_client.utils import create_paginated_query

app = typer.Typer(help="Shopify GraphQL API CLI")
console = Console()

T = TypeVar("T")


def async_command(f: Callable[..., T]) -> Callable[..., T]:
    """Decorator to handle async Typer commands"""

    @wraps(f)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        return cast(T, asyncer.runnify(f)(*args, **kwargs))

    return wrapper


@app.command()
@async_command
async def products(
    store: str = typer.Argument(..., help="Your store's myshopify.com domain"),
    access_token: str = typer.Argument(..., help="Your app's access token"),
    limit: int = typer.Option(500, help="Number of products to fetch"),
    fields: list[str] = typer.Option(
        ["id", "title", "handle", "createdAt"],
        help="Fields to fetch for each product",
    ),
) -> None:
    """Fetch products with pagination"""
    query = create_paginated_query("products", fields, first=min(limit, 250))

    async with ShopifyClient(store, access_token) as client:
        results = await client.graphql_call_with_pagination(query, max_limit=limit)
        if not results:
            console.print("[red]No products found[/red]")
            return

        # Create table
        table = Table(title=f"Products from {store}")
        for field in fields:
            table.add_column(field)

        for product in results:
            table.add_row(*[str(product.get(field, "")) for field in fields])

        console.print(table)
        console.print(f"\nTotal products fetched: {len(results)}")


if __name__ == "__main__":
    app()
