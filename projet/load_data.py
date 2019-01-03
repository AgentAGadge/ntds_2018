import argparse
import json
import numpy as np
import pandas as pd
import pickle
import requests
from scipy.spatial.distance import pdist, squareform

RESULT_OFFSET = 20
WEIGHTS_THRESHOLD = 0.5; 

ADJACENCY_FNAME = "adjacency.npy"
FEATURES_FNAME = "vote_positions.pickle"
LABELS_FNAME = "active_senators.pickle"
URL_ROOT = "https://api.propublica.org/congress/v1"

URL_MEMBERS = lambda congress, chamber: f"{URL_ROOT}/{congress}/{chamber}/members.json"
URL_VOTES = lambda member, offset: f"{URL_ROOT}/members/{member}/votes.json?offset={offset}"
URL_COSPONS = lambda member, offset: f"{URL_ROOT}/members/{member}/bills/cosponsored.json?offset={offset}"
URL_COSPONS_BILL = lambda bill, congress : f"{URL_ROOT}/{congress}/bills/{bill}/cosponsors.json"
VOTE_ID = lambda congress, session, roll_call: f"C{congress}:S{session}:C{roll_call}"


def get_from_api(url, *, verbose=False):
    """ Performs GET request to URL with the ProPublica API Key header """
    vprint = lambda *a, **kwa: print(*a, **kwa) if verbose else None

    with open("APIKey.txt", 'r') as key_file:
        api_key=key_file.readline()
        if api_key[-1] == '\n':
            api_key = api_key[:-1]
            
    headers = {'X-API-Key': api_key}
    vprint("getting", url, "with headers", headers, "...")
    r = requests.get(url, headers=headers)
    vprint("...done")
    return r


def _get(url, *, verbose=False):
    """ Gets Response at url and returns JSON dict form of response """ 
    r = get_from_api(url, verbose=verbose)
    d = json.loads(r.content)
    return d["results"][0]


def filter_active_senators(senators, *, verbose=False):
    """ Filters out the senators not in office anymore """
    vprint = lambda *a, **kwa: print(*a, **kwa) if verbose else None
    active_senators = [s for s in senators if s["in_office"]]
    vprint(f"There are {len(active_senators)} active senators among the {len(senators)} senators")
    return active_senators


def get_active_senators(*, congress=115, chamber="senate", verbose=False, compact=False):
    """
    Given congress and chamber, fetches active senators
    Args:
        congress: number of congress fetched
        chamber: [senate|house] chamber fetched
        verbose: set to True for debugging information
        compact: set to True to get a list of 4-tuples with important info instead of json dict list
    Returns:
        list of tuple (id, fname, lname, party) if compact=True, otherwise list of members json
    """
    COMPACT_KEYS = ("id", "first_name", "last_name", "party")

    ans = _get(URL_MEMBERS(congress, chamber), verbose=verbose)
    members = ans["members"]    
    active_senators = filter_active_senators(members)
    return [[m.get(k, "NULL") for k in COMPACT_KEYS] for m in active_senators] if compact else active_senators


def votes_from_offset(member_id, offset, *, verbose=False):
    """
    """
    ans = _get(URL_VOTES(member_id, offset), verbose=verbose)
    votes = ans["votes"]
    
    compact = [{"id": VOTE_ID(vote['congress'], vote['session'], vote['roll_call']), "position": vote['position']} for vote in votes]
    
    return compact


def df_from_votes(active_senators, requests_per_senator, *, verbose=False):
    """
    """
    df_generator = []

    for senator in active_senators:
        
        senator_dict = {}
        member_id = senator["id"]

        for offset in range(0, requests_per_senator*RESULT_OFFSET, RESULT_OFFSET):
            votes = votes_from_offset(member_id, offset)

            for vote in votes:
                vote_id = vote["id"]
                position = vote["position"]
                senator_dict[vote_id] = position

        df_generator.append(senator_dict)

    labels = pd.io.json.json_normalize(active_senators)
    features = pd.io.json.json_normalize(df_generator)

    return labels, features


def create_adjacency(features):
    """
    Compute the weigths of the network
    """
    #Convert features to numbers
    features = features.replace('Yes', 1)
    features = features.replace('No', 0)

    #All others values should be NaN
    cols = features.columns
    features[cols] = features[cols].apply(pd.to_numeric, errors='coerce')

    #Define a distance ignoring the NaN values
    def l1_normalized_without_NaN(x, y):
        return  np.nansum((np.absolute(x-y)))/np.count_nonzero(~np.isnan(x-y))

    distances = pdist(features.values, l1_normalized_without_NaN)

    #Distances to weights
    kernel_width = distances.mean()
    weights = np.exp(-distances**2 / kernel_width**2)

    # Turn the list of weights into a matrix.
    adjacency = squareform(weights)
    adjacency[adjacency < WEIGHTS_THRESHOLD] = 0

    return adjacency


def get_bills_cosponsored(member_id, offset, *, verbose=False):
    """ Fetches the list of bill_id cosponsored by member """

    ans = _get(URL_COSPONS(member_id, offset), verbose=verbose)
    bills = ans["bills"]
    return [bill["bill_id"] for bill in bills]


def get_cosponsors(bill_id, *,verbose = False):
    """ Fetches the list of cosponsors for a specific bill """
    
    ans = _get(URL_COSPONS_BILL(bill_id, 115), verbose=verbose)
    cosponsors = ans["cosponsors"]
    return [cosponsor["cosponsor_id"] for cosponsor in cosponsors]


def main(*, requests_per_senator=1, adjacency=False, verbose=True):

    if adjacency: 
        active_senators = get_active_senators()
        labels, features = df_from_votes(active_senators, requests_per_senator)
        labels.to_pickle(LABELS_FNAME)
        features.to_pickle(FEATURES_FNAME)
        adjacency = create_adjacency(features)
        np.save(ADJACENCY_FNAME, adjacency)

    return 0

if __name__=="__main__":
    # Defines all parser arguments when launching the script directly in terminal
    parser = argparse.ArgumentParser()
    parser.add_argument("-adj", "--adjacency", help="get vote data and create adjacency matrix",
                        action="store_true")
    parser.add_argument("--requests", type=int, default=1, help="requests per senator")

    args = parser.parse_args()

    main(requests_per_senator=args.requests, adjacency=args.adjacency)