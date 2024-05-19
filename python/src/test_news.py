import requests

url = "https://api.benzinga.com/api/v2/news"

querystring = {"token":"cb802b512a594f6985a545482e362c5e","page":"1","channels":"News","authors":"Murtuza Merchant"}

headers = {"accept": "application/json"}

response = requests.request("GET", url, headers=headers, params=querystring)

print(response.text)