import os 


API_KEY = "APIKey.txt"
CHAMBER = "senate"
CONGRESS = 115
DATA_PATH = "data"
RESULT_OFFSET = 20
SEED = 2018 #Used for randomness throughout the project
URL_ROOT = "https://api.propublica.org/congress/v1"
WEIGHTS_THRESHOLD = 0.5

ACTIVE_SENATORS_FNAME = os.path.join(DATA_PATH, "active_senators.npy")
ADJACENCY_FNAME = os.path.join(DATA_PATH, "adjacency.npy")
COMMITTEES_FNAME = os.path.join(DATA_PATH, "committees.json")
COMMMITTEE_MEMBERS_FNAME = os.path.join(DATA_PATH, "committee_members.json")
BILLS_FNAME = os.path.join(DATA_PATH, "bills.json")
COSPONSORED_FNAME = os.path.join(DATA_PATH, "cosponsored.pickle")
COSPONSORS_FNAME = os.path.join(DATA_PATH, "cosponsors.pickle")
PARTY_FNAME = os.path.join(DATA_PATH, "party.npy")
VOTE_POSITIONS_FNAME = os.path.join(DATA_PATH, "vote_positions.pickle")
VOTES_FNAME = os.path.join(DATA_PATH, "votes.pickle")

URL_COMMITTEES = lambda congress, chamber: f"{URL_ROOT}/{congress}/{chamber}/committees.json"
URL_COSPONS = lambda member, offset: f"{URL_ROOT}/members/{member}/bills/cosponsored.json?offset={offset}"
URL_COSPONS_BILL = lambda bill, congress : f"{URL_ROOT}/{congress}/bills/{bill}/cosponsors.json"
URL_MEMBERS = lambda congress, chamber: f"{URL_ROOT}/{congress}/{chamber}/members.json"
URL_VOTES = lambda member, offset: f"{URL_ROOT}/members/{member}/votes.json?offset={offset}"
VOTE_ID = lambda congress, session, roll_call: f"C{congress}:S{session}:C{roll_call}"
