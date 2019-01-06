import argparse
import collections
import json
import numpy as np
import os
import pandas as pd
import pickle
import requests
from scipy.spatial.distance import pdist, squareform

import common


def get_from_api(url, *, verbose=False):
    """ Performs GET request to URL with the ProPublica API Key header """
    vprint = lambda *a, **kwa: print(*a, **kwa) if verbose else None

    with open("APIKey2.txt", 'r') as key_file:
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
    return [] if "results" not in d else d["results"][0]


def filter_active_senators(senators, *, verbose=False):
    #Filters out the senators not in office anymore 
    vprint = lambda *a, **kwa: print(*a, **kwa) if verbose else None
    active_senators = [s for s in senators if s["in_office"]]
    vprint(f"There are {len(active_senators)} active senators among the {len(senators)} senators")
    return active_senators


def query_active_senators(*, congress=115, chamber="senate", verbose=False, compact=False):
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

    ans = _get(common.URL_MEMBERS(congress, chamber), verbose=verbose)
    if ans: 
        members = ans["members"]    
        active_senators = filter_active_senators(members)
        return [[m.get(k, "NULL") for k in COMPACT_KEYS] for m in active_senators] if compact else active_senators
    else:
        return []


def votes_from_offset(member_id, offset, *, verbose=False):
    """
    """
    ans = _get(common.URL_VOTES(member_id, offset), verbose=verbose)
    if ans:
        votes = ans["votes"]
        #add unique id to vote
        for vote in votes:
            vote["id"] = common.VOTE_ID(vote['congress'], vote['session'], vote['roll_call'])

        return votes
    else:
        return []


def flatten(d, parent_key='', sep='.'):
    items = []
    for k, v in d.items():
        new_key = parent_key + sep + k if parent_key else k
        if isinstance(v, collections.MutableMapping):
            items.extend(flatten(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def df_from_votes(senators, requests_per_senator, *, verbose=False):
    """
    """
    position_generator = []
    vote_generator = []

    for i, senator in enumerate(senators):
        
        senator_dict = {}
        member_id = senator["id"]

        info = f"{i+1}/{len(senators)} Getting the last {requests_per_senator * common.RESULT_OFFSET} votes of senator {member_id}"
        print(info)

        for offset in range(0, requests_per_senator*common.RESULT_OFFSET, common.RESULT_OFFSET):
            votes = votes_from_offset(member_id, offset)

            for vote in votes:
                vote_id = vote["id"]
                position = vote["position"]
                senator_dict[vote_id] = position
                vote_generator.append(flatten(vote))

        position_generator.append(senator_dict)

    vote_positions = pd.io.json.json_normalize(position_generator)
    
    votes = pd.io.json.json_normalize(vote_generator)
    votes.drop(columns=["member_id", "position"])
    votes.drop_duplicates(inplace=True)

    return vote_positions, votes


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
    adjacency[adjacency < common.WEIGHTS_THRESHOLD] = 0

    return adjacency


def cosponsored_from_offset(member_id, offset, *, verbose=False):
    """ Fetches the list of bill_id cosponsored by member """

    ans = _get(common.URL_COSPONS(member_id, offset), verbose=verbose)
    if ans:
        bills = ans["bills"]
        return [bill["bill_id"] for bill in bills]
    else:
        return []


def cosponsored_bills(senator_ids, requests_per_senator, *, verbose=False):
    #Structure to keep the cosponsored bills
    cosponsored = {s_id: [] for s_id in senator_ids}

    for i, s_id in enumerate(senator_ids):
        
        info = f"{i+1}/{len(senator_ids)} Getting the last {requests_per_senator * common.RESULT_OFFSET} bills cosponsored by senator {s_id}"
        print(info)
            
        for offset in range(0, requests_per_senator * common.RESULT_OFFSET, common.RESULT_OFFSET):
            bills = cosponsored_from_offset(s_id, offset, verbose=verbose)
            cosponsored[s_id].extend(bills)
    
    return cosponsored


def get_cosponsors(bill_id, *,verbose = False):
    """ Fetches the list of cosponsors for a specific bill """
    
    ans = _get(common.URL_COSPONS_BILL(bill_id, 115), verbose=verbose)
    if ans:
        cosponsors = ans["cosponsors"]
        return [cosponsor["cosponsor_id"] for cosponsor in cosponsors]
    else:
        return []


def main(*, requests_per_senator=1, get_active_senators=False, get_adjacency=False, get_cosponsorship=False, verbose=True):

    if not os.path.isdir(common.DATA_PATH):
        os.mkdir(common.DATA_PATH)

    """
    if get_active_senators:
        active_senators = query_active_senators()
        party = [s["party"] for s in active_senators]
        np.save(common.ACTIVE_SENATORS_FNAME, active_senators)
        np.save(common.PARTY_FNAME, party)
    """

    if get_adjacency: 
        senators = np.load(common.ACTIVE_SENATORS_FNAME)
        vote_positions, votes = df_from_votes(senators, requests_per_senator)
        adjacency = create_adjacency(vote_positions)

        vote_positions.to_pickle(common.VOTE_POSITIONS_FNAME)
        votes.to_pickle(common.VOTES_FNAME)
        np.save(common.ADJACENCY_FNAME, adjacency)

    if get_cosponsorship:
        senators = np.load(common.ACTIVE_SENATORS_FNAME)
        senator_ids = [s["id"] for s in senators]
        cosponsored = cosponsored_bills(senator_ids, requests_per_senator)
        
        with open(common.COSPONSORED_FNAME, "wb") as cosp_ser:
            pickle.dump(cosponsored, cosp_ser, protocol=pickle.HIGHEST_PROTOCOL)
        

    return 0


if __name__=="__main__":
    # Defines all parser arguments when launching the script directly in terminal
    parser = argparse.ArgumentParser()
    parser.add_argument("-as", "--active_senators", help="get list of active senators",
                        action="store_true")
    parser.add_argument("-adj", "--adjacency", help="get vote data and create adjacency matrix",
                        action="store_true")                    
    parser.add_argument("-cs", "--cosponsorship", help="get cosponsorship data and create commonality matrix",
                        action="store_true")
    parser.add_argument("--requests", type=int, default=1, help="requests per senator")

    args = parser.parse_args()

    main(requests_per_senator=args.requests, get_active_senators=args.active_senators, get_adjacency=args.adjacency, get_cosponsorship=args.cosponsorship)