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

    with open(common.API_KEY, 'r') as key_file:
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


def query_active_senators(*, congress=common.CONGRESS, chamber=common.CHAMBER, verbose=False, compact=False):
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
        # add integer id
        for id_num, senator in enumerate(active_senators):
            senator["id_num"] = id_num
        return [[m.get(k, "NULL") for k in COMPACT_KEYS] for m in active_senators] if compact else active_senators
    else:
        return []


def votes_from_offset(member_id, offset, *, verbose=False):
    """
    Given a senator ID, fetches common.RESULT_OFFSET votes, starting at 'offset'
    Args:
        member_id: senator ID 
        offset: votes are retrieved after this value
        verbose: set to True for debugging information
    Returns:
        list of votes, with a unique ID for identifiability
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
    """
    Flattens a dictionary, that is recursively unpacks composite keys
    Args:
        d: dictionary to be flatten
        parent_key: prefix when a composite value is flattened recursively
        sep: seperator between key and composite value
    Returns:
        the flattened dictionary
    """
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
    Given a list of senators, retrieves voting data and constructs two DataFrame structures, 
    a first one that collects vote positions of senators on certain votes, and another one 
    that contains information about the votes
    Args:
        senators: list of senators
        requests_per_senator: number of URL requests per senator
        verbose: set to True for debugging information
    Returns:
        pandas DataFrame 'vote_positions' and 'votes'
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
    votes.drop(columns=["member_id", "position"], inplace=True)
    votes.drop_duplicates(inplace=True)

    return vote_positions, votes


def create_adjacency(features):
    """
    Builds an adjacency matrix based on the voting behavior of senators
    Args:
        features: DataFrame of senator's vote positions 
    Returns:
        the adjacency matrix as a numpy array
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
    """
    Given a list of senator IDs, retrieves a certain number of cosponsored bills
    Args:
        senator_ids: list of senators IDs
        requests_per_senator: number of URL requests per senator
        verbose: set to True for debugging information
    Returns:
        dict (K,V) where K is a senator ID and V is a set of cosponsored bills
    """
    #Structure to keep the cosponsored bills
    cosponsored = {s_id: [] for s_id in senator_ids}

    for i, s_id in enumerate(senator_ids):
        
        info = f"{i+1}/{len(senator_ids)} Getting the last {requests_per_senator * common.RESULT_OFFSET} bills cosponsored by senator {s_id}"
        print(info)
            
        for offset in range(0, requests_per_senator * common.RESULT_OFFSET, common.RESULT_OFFSET):
            bills = cosponsored_from_offset(s_id, offset, verbose=verbose)
            cosponsored[s_id].extend(bills)
    
    return cosponsored


def cosponsors_of_bill(bill_id, *, verbose=False):
    """ Fetches the list of cosponsors for a specific bill """
    
    bill, congress = bill_id.split('-')
    ans = _get(common.URL_COSPONS_BILL(bill, congress), verbose=verbose)
    if ans:
        cosponsors = ans["cosponsors"]
        return [cosponsor["cosponsor_id"] for cosponsor in cosponsors]
    else:
        return []


def bills_cosponsors(bill_ids, *, verbose=False):
    """
    Given a list of bill IDs, retrieves the list of cosponsors
    Args:
        bill_ids: list of bill IDs
        verbose: set to True for debugging information
    Returns:
        dict (K,V) where K is a bill ID and V the list of cosponsors
    """
    return {bill_id: cosponsors_of_bill(bill_id, verbose=verbose) for bill_id in bill_ids}


def query_committees(*, congress=common.CONGRESS, chamber=common.CHAMBER, verbose=False):
    """ Fetches the list of committees """

    ans = _get(common.URL_COMMITTEES(congress, chamber), verbose=verbose)
    return ans["committees"]


def get_members_from_committees_json(*, write_to_disk=True, verbose=False):
    """ Opens the committee json and produces the committee_members json from it """
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


def get_bills_committees():
    """ Returns mapping from bill_id to list of committee codes sourcing this bill """
    with open(common.BILLS_FNAME) as fp:
        bills = json.load(fp)
    return {b["bill_id"] : b["committee_codes"] for b in bills}

def main(*, requests_per_senator=1, get_active_senators=False, get_adjacency=False,\
        get_cosponsorship=False, get_cosponsors=False, get_committees=False, verbose=False):
    """
    Given congress and chamber, fetches active senators
    Args:
        requests_per_senators: number of URL requests per senator
        get_active_senators: boolean set True if the list of active senators should be retrieved and saved
        get_adjacency: boolean set True if the initial adjacency matrix should be recomputed and saved
        get_cosponsorship: boolean set True if the list of cosponsored bills by senators should be retrieved and saved
        get_cosponsors: boolean set True if, for certain bills, the list of cosponsors should be retrieved and saved 
        get_committees: boolean set True if committee data should be retrieved and saved
    """

    if not os.path.isdir(common.DATA_PATH):
        os.mkdir(common.DATA_PATH)

    """
    if get_active_senators:
        active_senators = query_active_senators(verbose=verbose)
        party = [s["party"] for s in active_senators]
        np.save(common.ACTIVE_SENATORS_FNAME, active_senators)
        np.save(common.PARTY_FNAME, party)
    """

    if get_adjacency: 
        senators = np.load(common.ACTIVE_SENATORS_FNAME)
        vote_positions, votes = df_from_votes(senators, requests_per_senator, verbose=verbose)
        adjacency = create_adjacency(vote_positions)

        vote_positions.to_pickle(common.VOTE_POSITIONS_FNAME)
        votes.to_pickle(common.VOTES_FNAME)
        np.save(common.ADJACENCY_FNAME, adjacency)

    if get_cosponsorship:
        senators = np.load(common.ACTIVE_SENATORS_FNAME)
        senator_ids = [s["id"] for s in senators]
        cosponsored = cosponsored_bills(senator_ids, requests_per_senator, verbose=verbose)
        
        with open(common.COSPONSORED_FNAME, "wb") as ser_dict:
            pickle.dump(cosponsored, ser_dict, protocol=pickle.HIGHEST_PROTOCOL)
        
    if get_cosponsors:
        votes = pd.read_pickle(common.VOTES_FNAME)
        bill_ids = votes["bill.bill_id"].values
        check_syntax = lambda bill_id: len(bill_id.split('-')) == 2
        valid_bill_ids = [bill_id for bill_id in bill_ids if isinstance(bill_id, str) and check_syntax(bill_id)]
        unique_bill_ids = np.unique(valid_bill_ids)
        cosponsors = bills_cosponsors(unique_bill_ids, verbose=verbose)
        
        with open(common.COSPONSORS_FNAME, "wb") as ser_dict:
            pickle.dump(cosponsors, ser_dict, protocol=pickle.HIGHEST_PROTOCOL)

    if get_committees:
        # Gets committee data from API and stores it in json files
        committees = query_committees(congress=common.CONGRESS, verbose=verbose)
        with open(common.COMMITTEES_FNAME, "w") as fp:
            json.dump(committees, fp, indent=4)

    return 0


if __name__=="__main__":
    # Defines all parser arguments when launching the script directly in terminal
    parser = argparse.ArgumentParser()
    parser.add_argument("-as", "--active_senators", help="get list of active senators",
                        action="store_true")
    parser.add_argument("-adj", "--adjacency", help="get vote data and create adjacency matrix",
                        action="store_true")                    
    parser.add_argument("-css", "--cosponsorship", help="get cosponsorship data and create commonality matrix",
                        action="store_true")
    parser.add_argument("-csp", "--cosponsors", help="get list of cosponsors of certain bills",
                        action="store_true")
    parser.add_argument("-cmt", "--committees", help="get committees data and creates npy files",
                        action="store_true")
    parser.add_argument("--requests", type=int, default=1, help="requests per senator")

    args = parser.parse_args()

    main(requests_per_senator=args.requests, get_active_senators=args.active_senators,\
        get_adjacency=args.adjacency, get_cosponsorship=args.cosponsorship, \
        get_cosponsors=args.cosponsors, get_committees=args.committees)
