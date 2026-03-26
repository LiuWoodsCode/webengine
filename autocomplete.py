import requests

SUGGEST_URL = "https://suggestqueries.google.com/complete/search"

def autocomplete(query, client="firefox", timeout=5):
    """
    Fetch Google autocomplete suggestions for a query.

    Returns a list of suggestion strings.
    """
    params = {
        "client": client,
        "q": query
    }

    resp = requests.get(SUGGEST_URL, params=params, timeout=timeout)
    resp.raise_for_status()

    data = resp.json()

    # data[1] is the list of suggestions
    return data[1]


if __name__ == "__main__":
    # tiny demo
    for s in autocomplete("hello"):
        print("-", s)
