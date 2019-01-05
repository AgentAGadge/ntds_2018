
import json

from load_data import COMMITTEES_FNAME, _get

COMMMITTEE_MEMBERS_FNAME = "committee_members.json"

def get_members_from_committees_json(*, write_to_disk=True, verbose=False):
    vprint = lambda *a, **kwa: print(*a, **kwa) if verbose else None

    with open(COMMITTEES_FNAME) as fp:
        committees = json.load(fp)

    committee_members = {}

    for c in committees:
        vprint("Fetching", c["id"], c["name"][:64], "at", c["api_uri"])
        ans = _get(c["api_uri"])
        committee_members[c["id"]] = [m["id"] for m in ans["current_members"]]
        
    if write_to_disk:
        with open(COMMMITTEE_MEMBERS_FNAME, "w") as fp:
            json.dump(committee_members, fp, indent=4)
    
    return committee_members

if __name__=="__main__":
    get_members_from_committees_json(verbose=True)
