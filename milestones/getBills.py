
from getFromAPI import member_id, bills_cosponsored

senator = "Lamar Alexander"
member_id = member_id(*senator.split())
bills = bills_cosponsored(member_id)

print(f"Last {len(bills)} bills sponsored by {senator} : {bills}")
