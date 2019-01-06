import os 

RESULT_OFFSET = 20
SEED = 2018 #Used for randomness throughout the project 
WEIGHTS_THRESHOLD = 0.5

DATA_PATH = "data"
URL_ROOT = "https://api.propublica.org/congress/v1"

ACTIVE_SENATORS_FNAME = os.path.join(DATA_PATH, "active_senators.npy")
ADJACENCY_FNAME = os.path.join(DATA_PATH, "adjacency.npy")
COSPONSORED_FNAME = os.path.join(DATA_PATH, "cosponsored.pickle")
COMMITTEES_FNAME = os.path.join(DATA_PATH, "committees.json")
PARTY_FNAME = os.path.join(DATA_PATH, "party.npy")
VOTE_POSITIONS_FNAME = os.path.join(DATA_PATH, "vote_positions.pickle")
VOTES_FNAME = os.path.join(DATA_PATH, "votes.pickle")

URL_COMMITTEES = lambda congress, chamber: f"{URL_ROOT}/{congress}/{chamber}/committees.json"
URL_COSPONS = lambda member, offset: f"{URL_ROOT}/members/{member}/bills/cosponsored.json?offset={offset}"
URL_COSPONS_BILL = lambda bill, congress : f"{URL_ROOT}/{congress}/bills/{bill}/cosponsors.json"
URL_MEMBERS = lambda congress, chamber: f"{URL_ROOT}/{congress}/{chamber}/members.json"
URL_VOTES = lambda member, offset: f"{URL_ROOT}/members/{member}/votes.json?offset={offset}"
VOTE_ID = lambda congress, session, roll_call: f"C{congress}:S{session}:C{roll_call}"