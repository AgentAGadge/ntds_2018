import requests
import json

URL_ROOT = "https://api.propublica.org/congress/v1"
URL_MEMBERS = lambda congress, chamber: f"{URL_ROOT}/{congress}/{chamber}/members.json"
URL_COSPONS = lambda member: f"{URL_ROOT}/members/{member}/bills/cosponsored.json"

def get_from_api(url, *, verbose=False):
    """ Performs GET request to URL with the ProPublica API Key header """
    vprint = lambda *a, **kwa: print(*a, **kwa) if verbose else None

    with open("APIKey.txt", "r") as keyFile:
        apiKey=keyFile.readline()
        if apiKey[-1] == '\n':
            apiKey = apiKey[:-1]
            
    headers = {'X-API-Key': apiKey}
    vprint("getting", url, "with headers", headers, "...")
    r = requests.get(url, headers=headers)
    vprint("...done")
    return r

def _get(url, *, verbose=False):
    """ Gets Response at url and returns JSON dict form of response """ 
    r = get_from_api(url, verbose=verbose)
    return json.loads(r.content)

def get_members(*, congress=115, chamber="senate", verbose=False, compact=False):
    """
    Fetches the current house members
    Args:
        congress: number of congress fetched
        chamber: [senate|house] chamber fetched
        verbose: set to True for debugging information
        compact: set to True to get a list of 4-tuples with important info instead of json dict list
    Returns:
        list of tuple (id, fname, lname, party) if compact=True, otherwise list of members json
    """
    COMPACT_KEYS = ("id", "first_name", "last_name", "party")

    ans = _get(URL_MEMBERS(115, "senate"), verbose=verbose)
    members = ans["results"][0]["members"]    
    return [[m.get(k, "NULL") for k in COMPACT_KEYS] for m in members] if compact else members

def get_bills_cosponsored(member_id, *, verbose=False):
    """ Fetches the list of bill_id cosponsored by member """

    ans = _get(URL_COSPONS(member_id), verbose=verbose)
    bills = ans["results"][0]["bills"]
    return [bill["bill_id"] for bill in bills]

def get_member_id(fname, lname, *, verbose=False):
    """ Fetches the ID of the member with first and last name """
    members = get_members(verbose=verbose, compact=True)
    for m in members:
        if m[1] == fname and m[2] == lname:
            return m[0]
    return None

def filter_active_senators(senators, *, verbose=False):
    """ Filters out the senators not in office anymore """
    vprint = lambda *a, **kwa: print(*a, **kwa) if verbose else None
    active_senators = [s for s in senators if s["in_office"]]
    vprint(f"There are {len(active_senators)} active senators among the {len(senators)} senators")
    return active_senators
