import requests
import json

URL_ROOT = "https://api.propublica.org/congress/v1"
URL_MEMBERS = lambda congress, chamber: f"{URL_ROOT}/{congress}/{chamber}/members.json"
URL_COSP = lambda member: f"{URL_ROOT}/members/{member}/bills/cosponsored.json"

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

def house_members(*, verbose=False):
    """ Fetches the current house members, returns list of tuple (id, fname, lname, party) """
    ro = _get(URL_MEMBERS(115, "senate"), verbose=verbose)
    return [[m.get(k, "NULL") for k in ("id", "first_name", "last_name", "party")]
            for m in ro["results"][0]["members"]]

def bills_cosponsored(member_id, *, verbose=False):
    """ Fetches the list of bill_id cosponsored by member """

    ro = _get(URL_COSP(member_id), verbose=verbose)
    bills = ro["results"][0]["bills"]
    return [bill["bill_id"] for bill in bills]

def member_id(fname, lname, *, verbose=False):
    """ Fetches the ID of the member with first and last name """
    members = house_members(verbose=verbose)
    for m in members:
        if m[1] == fname and m[2] == lname:
            return m[0]
    return None
