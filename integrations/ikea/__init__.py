"""IKEA as a ProductSource for GhostBuild product discovery (outside core: core never names a retailer).

Search = Anthropic's documented server-side web_search tool restricted to ikea.com (allowed_domains). Every candidate it returns is
then validated by reading the official ikea.com product page itself; the model never writes a name, picture or number that is shown.
No undocumented IKEA API is used."""
