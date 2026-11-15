### keenable_search
web search via Keenable. returns title, url and snippet per result.
use when search_engine returns nothing or errors, or when the user asks for Keenable.
works without a key; on a rate limit it says so and falls back to SearXNG.
args: `query`
usage:
~~~json
{
    "thoughts": ["search_engine returned nothing, trying Keenable"],
    "tool_name": "keenable_search",
    "tool_args": {
        "query": "latest python release"
    }
}
~~~
