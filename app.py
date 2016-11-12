import os
import sys
import json
import httplib, urllib
import requests
from flask import Flask, request
from model_extension import sanitize_input, classify
import psycopg2
import os
import urlparse
import json

app = Flask(__name__)

#https://blog.hartleybrody.com/fb-messenger-bot/
#https://alfred-heroku.herokuapp.com/
#https://devcenter.heroku.com/articles/heroku-postgresql    DATABASE_URL
# terminal: heroku pg:psql

@app.route('/', methods=['GET'])
def verify():
	# when the endpoint is registered as a webhook, it must echo back
	# the 'hub.challenge' value it receives in the query arguments
	if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.challenge"):
		if not request.args.get("hub.verify_token") == os.environ["VERIFY_TOKEN"]:
			return "Verification token mismatch", 403
		return request.args["hub.challenge"], 200

	return "Hello world - 2", 200


@app.route('/', methods=['POST'])
def webhook():

	# endpoint for processing incoming messaging events
	try:
		data = request.get_json()
		if data["object"] == "page":

			for entry in data["entry"]:
				for messaging_event in entry["messaging"]:
					if messaging_event.get("message"):  # someone sent us a message
						sender_id = messaging_event["sender"]["id"]		# the facebook ID of the person sending you the message
						#ignore case where alfred is the sender
						if sender_id == '1885643518323254':
							continue
						recipient_id = messaging_event["recipient"]["id"]  # the recipient's ID, which should be your page's facebook ID
						if messaging_event["message"].get("text"):
							message_text = messaging_event["message"]["text"]  # the message's text
							response = get_response(message_text, sender_id)
							send_message(sender_id, response)

					if messaging_event.get("delivery"):  # delivery confirmation
						pass
					if messaging_event.get("optin"):  # optin confirmation
						pass
					if messaging_event.get("postback"):  # user clicked/tapped "postback" button in earlier message
						pass
		return "ok", 200

	except Exception, e:
		log("ERROR: " + str(e))
		return "internal server error", 500

@app.route('/oauth', methods=['GET'])
def oauth():
	log(str(request.args))
	if 'code' in request.args:
		code = request.args.get('code')
		params = urllib.urlencode({'grant_type':'authorization_code', 'code':code, 'client_id':'b882249a-a9b4-4690-935d-bf78aeeb991a', 'client_secret':'6d42b99f-0ac1-45fe-b70f-2a4556842bed', 'redirect_url':'https://alfred-heroku.herokuapp.com/oauth'})
		headers = {"Content-type": "application/x-www-form-urlencoded","Accept": "text/plain"}
		conn = httplib.HTTPSConnection("graph.api.smartthings.com")
		conn.request("POST", "/oauth/token", params, headers)
		response = conn.getresponse()
		log(response.read())
	else:
		log(str(request.args))

	return "ok", 200

def handle_smartthings_request_get(endpoint):
	#GET -H "Authorization: Bearer ACCESS-TOKEN" "https://graph.api.smartthings.com/api/smartapps/endpoints"
	authorization = "Bearer 4285e326-bb70-47b5-bf2b-02c3462609ae"
	url = "https://graph-na02-useast1.api.smartthings.com:443/api/smartapps/installations/6536ba39-04c9-4cd2-9759-56da43b45da7/" + endpoint
	r=requests.get(url, headers={"Authorization":authorization})
	log(r.text)
	json_data = json.loads(r.text)
	return json_data


def handle_smartthings_request_get_test(endpoint):
	#GET -H "Authorization: Bearer ACCESS-TOKEN" "https://graph.api.smartthings.com/api/smartapps/endpoints"
	authorization = "Bearer 4285e326-bb70-47b5-bf2b-02c3462609ae"
	url = "https://graph-na02-useast1.api.smartthings.com:443/api/smartapps/installations/6536ba39-04c9-4cd2-9759-56da43b45da7/" + endpoint
	r=requests.get(url, headers={"Authorization":authorization})
	log(r.text)

def handle_smartthings_request_put(endpoint):
	authorization = "Bearer 4285e326-bb70-47b5-bf2b-02c3462609ae"
	url = "https://graph-na02-useast1.api.smartthings.com:443/api/smartapps/installations/6536ba39-04c9-4cd2-9759-56da43b45da7/" + endpoint
	r=requests.put(url, headers={"Authorization":authorization})
	#log(url)

def get_response(input_command, sender_id):
	input_command = input_command.lower()

	# sanitize input
	sanitized_command = sanitize_input(input_command)

	# get result (int)
	classification_code = classify(sanitized_command)

	# log input
	#log_message(sender_id, input_command, classification_code)

	# return response
	if(classification_code == 0):
		return "Sorry, I don't understand."

	elif(classification_code == 1):
		json_response = handle_smartthings_request_get("bulb")
		if json_response[1]['value'] == 'off':
			return "Your light is already off."
		handle_smartthings_request_put("bulb/off")
		return "I've turned your light off."

	elif(classification_code == 2):
		json_response = handle_smartthings_request_get("bulb")
		if json_response[1]['value'] == 'on':
			return "Your light is already on."
		handle_smartthings_request_put("bulb/on")
		return "I've turned your light on."

	elif(classification_code == 3):
		handle_smartthings_request_put("bulb/dim")
		return "Your light is now dimmed to 20%."

	elif(classification_code == 4):
		handle_smartthings_request_put("bulb/brighten")
		return "Your light is now brightened to 100%."

	elif(classification_code == 5):
		json_response = handle_smartthings_request_get("bulb")
		if json_response[1]['value'] == 'on':
			return "Your light is on at " + str(json_response[0]['value']) + "%."
		else:
			return "Your light is off."

	elif(classification_code == 6):
		json_response = handle_smartthings_request_get("cameraMotion")
		if True:
			return "I detected motion recently TODO."
		else:
			return "I have not detected motion recently TODO."

	elif(classification_code == 7):
		#json_response = handle_smartthings_request_get("takePicture")
		send_picture_message(sender_id)
		return "Here is a current picture from your camera TODO."

	elif(classification_code == 8):
		#handle_smartthings_request_get_test("doorStatus")
		return "I'm trying to access your door sensor TODO."
	#9 color

	else:
		return "Unknown classification code received by model."

def send_message(recipient_id, message_text):

	#log("sending message to {recipient}: {text}".format(recipient=recipient_id, text=message_text))

	params = {
		"access_token": os.environ["PAGE_ACCESS_TOKEN"]
	}
	headers = {
		"Content-Type": "application/json"
	}
	data = json.dumps({
		"recipient": {
			"id": recipient_id
		},
		"message": {
			"attachment": { #comment out the attachment for non-test mode
				"type": "template",
				"payload": {
					"template_type": "button",
					"text": message_text,
					"buttons": [
						{
							"type": "postback",
							"title": "Correct, good job Alfred",
							"payload": "works"
						},
						{
							"type": "postback",
							"title": "Incorrect, bad Alfred",
							"payload": "broken"
						}
					]
				}
			}
		}
	})
	r = requests.post("https://graph.facebook.com/v2.6/me/messages", params=params, headers=headers, data=data)
	if r.status_code != 200:
		log(r.status_code)
		log(r.text)

def send_picture_message(recipient_id):

	log("sending message to {recipient}: {text}".format(recipient=recipient_id, text="picture message."))

	params = {
		"access_token": os.environ["PAGE_ACCESS_TOKEN"]
	}
	headers = {
		"Content-Type": "application/json"
	}
	data = json.dumps({
		"recipient": {
			"id": recipient_id
		},
		"message": {
			"attachment":{
				"type": "image",
				"payload":{
					#"url":"http://media.mlive.com/kzgazette_impact/photo/12627792-small.jpg"
					"url":"https://scontent.xx.fbcdn.net/v/t1.0-9/15027448_1888608944693378_4139724658200573_n.jpg?oh=cca96f3729e407f5d9e0a9a3cb942e53&oe=58D26B09"
				}
			}
		}
	})
	r = requests.post("https://graph.facebook.com/v2.6/me/messages", params=params, headers=headers, data=data)
	if r.status_code != 200:
		log(r.status_code)
		log(r.text)

def log(message):  # simple wrapper for logging to stdout on heroku
	print str(message)
	sys.stdout.flush()

def log_message(sender_id, input_command, classification_code):
	urlparse.uses_netloc.append('postgres')
	url = urlparse.urlparse(os.environ['DATABASE_URL'])
	conn = psycopg2.connect(
	    database=url.path[1:],
	    user=url.username,
	    password=url.password,
	    host=url.hostname,
	    port=url.port
	)
	query = "INSERT INTO command_history(client_id, message_content, classified_result) VALUES (%s, %s, %s)"
	log_data = (str(sender_id), input_command, str(classification_code))
	cur = conn.cursor()
	cur.execute(query, log_data)
	conn.commit()
	conn.close()

def send_message_with_dropdown(recipient_id, message_text):

	log("sending message to {recipient}: {text}".format(recipient=recipient_id, text=message_text))

	params = {
		"access_token": os.environ["PAGE_ACCESS_TOKEN"]
	}
	headers = {
		"Content-Type": "application/json"
	}
	data = json.dumps({
		"recipient": {
			"id": recipient_id
		},
		"message": {
			"attachment": {
				"type": "template",
				"payload": {
					"template_type": "button",
					"text": message_text,
					"buttons": [
						{
							"type": "postback",
							"title": "Correct, good job Alfred",
							"payload": "asd"
						},
						{
							"type": "postback",
							"title": "Incorrect, bad Alfred",
							"payload": "psd"
						}
					]
				}
			}
		}
	})
	r = requests.post("https://graph.facebook.com/v2.6/me/messages", params=params, headers=headers, data=data)
	if r.status_code != 200:
		log(r.status_code)
		log(r.text)

if __name__ == '__main__':
	app.run(debug=True)
