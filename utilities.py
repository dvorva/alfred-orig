import urllib2

def get_authorization_code():
    auth_url = "https://graph.api.smartthings.com/oauth/authorize?response_type=code&client_id=b882249a-a9b4-4690-935d-bf78aeeb991a&scope=app&redirect_uri=http://localhost:4567/oauth/callback"
    return urllib2.urlopen(auth_url).read()

print get_authorization_code();
