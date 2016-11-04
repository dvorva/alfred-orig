import urllib2
import requests
from xml.dom.minidom import parse, parseString

def get_authorization_code():
    auth_url = "https://graph.api.smartthings.com/oauth/authorize?response_type=code&client_id=b882249a-a9b4-4690-935d-bf78aeeb991a&scope=app&redirect_uri=http://localhost:4567/oauth/callback"
    return

def get_request():
    auth_url = "https://graph.api.smartthings.com/oauth/authorize?response_type=code&client_id=b882249a-a9b4-4690-935d-bf78aeeb991a&scope=app&redirect_uri=http://localhost:4567/oauth/callback"
    response = urllib2.urlopen(auth_url).read()
    #requests.get(auth_url)

    #username afujii@umich.edu
    #password alfredpassword1
    #print r.status_code
    #print r.headers .content
    dom1 = parseString(response)
    print dom1


get_request()
