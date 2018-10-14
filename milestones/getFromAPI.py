import requests

def getFromAPI(url):
    #file = open("APIKey.txt")
    with open ("APIKey.txt", "r") as keyFile:
        apiKey=keyFile.readline()
        if apiKey[-1] == '\n':
            apiKey = apiKey[:-1]
            
    headers = {'X-API-Key': apiKey}
    
    r = requests.get(url, headers = headers)