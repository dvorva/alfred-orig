import os
import sys
import json
import httplib, urllib
import requests
from flask import Flask, request

app = Flask(__name__)

#https://blog.hartleybrody.com/fb-messenger-bot/
#https://alfred-heroku.herokuapp.com/

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
		log(data)  # you may not want to log every incoming message in production, but it's good for testing
		if data["object"] == "page":

			for entry in data["entry"]:
				for messaging_event in entry["messaging"]:
					if messaging_event.get("message"):  # someone sent us a message
						sender_id = messaging_event["sender"]["id"]		# the facebook ID of the person sending you the message
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

def get_response(input_command, sender_id):
	input_command = input_command.lower()

	# sanitize input
	# log input
	# get result (int)
	# return response

	requests_file = open("/app/chat_messages.txt", "a")
	requests_file.write('{"class": X, "commandText": "' + input_command + '"},')
	requests_file.close()

	if(input_command == "turn light on"):
		return "I've turned your lights on."

	elif(input_command == "turn light off"):
		return "I've turned your lights off."

	elif(input_command == "is my light on"):
		if True:
			return "Yes, your light is on."
		else:
			return "No, your light is off."

	elif(input_command == "turn light off"):
		if True:
			return "Yes, your light is off."
		else:
			return "No, your light is on."

	elif(input_command == "dim my light"):
		return "Your light has been dimmed 50%."

	elif(input_command == "brighten my light"):
		return "Your light has been brightened 50%."

	elif(input_command == "is there motion"):
		if True:
			return "Yes, I detected motion recently."
		else:
			return "No, I have not detected motion recently."

	elif(input_command == "send camera screenshot"):
		send_picture_message(sender_id)
		return "Here is a picture from your camera."
	else:
		return "Sorry, I didn't recognize your request."

def send_message(recipient_id, message_text):

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
			"text": message_text
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
					"url":"http://media.mlive.com/kzgazette_impact/photo/12627792-small.jpg"
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


if __name__ == '__main__':
	app.run(debug=True)
