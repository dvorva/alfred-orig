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
from colour import Color
import random

app = Flask(__name__)

#https://blog.hartleybrody.com/fb-messenger-bot/
#https://alfred-heroku.herokuapp.com/
#https://devcenter.heroku.com/articles/heroku-postgresql    DATABASE_URL
# terminal: heroku pg:psql

@app.route('/contact_sensor_close', methods=['GET'])
def groovy_test():
	log(request)

	bulb_response = handle_smartthings_request_get("bulb")
	color_response = handle_smartthings_request_get("color")

	if bulb_response[1]['value'] == 'on' or color_response[1]['value'] == 'on':
		params = {
			"access_token": os.environ["PAGE_ACCESS_TOKEN"]
		}
		headers = {
			"Content-Type": "application/json"
		}
		data = json.dumps({
			"recipient": {
				"id": 1186606104737968
			},
			"message": {
				"attachment": { #comment out the attachment for non-test mode
					"type": "template",
					"payload": {
						"template_type": "button",
						"text": "I see you may have just left, should I turn off your lights?",
						"buttons": [
							{
								"type": "postback",
								"title": "Yes",
								"payload": "Yes, please turn off the lights"
							},
							{
								"type": "postback",
								"title": "No",
								"payload": "Do not turn off lights"
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

	return "ok", 200

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
							if(response != "do not send"):
								send_message(sender_id, response)
					if messaging_event.get("delivery"):  # delivery confirmation
						pass
					if messaging_event.get("optin"):  # optin confirmation
						pass
					if messaging_event.get("postback"):
						postback_text = messaging_event["postback"]["payload"]
						sender_id = messaging_event["sender"]["id"]
						if(postback_text == "Yes, please turn off the lights"):
							handle_smartthings_request_put("bulb/off")
							handle_smartthings_request_put("color/off")
							send_message(sender_id, "Your lights are now off")
						if(postback_text == "works"):
							update_result(sender_id, True)
						elif(postback_text == "broken"):
							update_result(sender_id, False)
						else:
							response = get_response(postback_text, sender_id)
							if(response != "do not send"):
								send_message(sender_id, response)

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
	url = "https://graph-na02-useast1.api.smartthings.com:443/api/smartapps/installations/cb4c79cf-4d24-4b01-ab87-5c9d54a29377/" + endpoint
	r=requests.get(url, headers={"Authorization":authorization})
	json_data = json.loads(r.text)
	return json_data

def handle_smartthings_request_put(endpoint):
	authorization = "Bearer 4285e326-bb70-47b5-bf2b-02c3462609ae"
	url = "https://graph-na02-useast1.api.smartthings.com:443/api/smartapps/installations/cb4c79cf-4d24-4b01-ab87-5c9d54a29377/" + endpoint
	r=requests.put(url, headers={"Authorization":authorization})
	#log(url)

def get_response(input_command, sender_id):
	input_command = input_command.lower()

	if(input_command == "party"):
		party()
		return "Hope you had fun! :^)"

	# sanitize input
	sanitized_command = sanitize_input(input_command)

	# get result (int)
	classification_code = classify(sanitized_command)

	# log input
	log_message(sender_id, input_command, classification_code)

	room_location = extract_location(sanitized_command)
	# return response
	if(classification_code == 0):
		return "Sorry, I don't understand."

	# TURN LIGHT OFF
	elif(classification_code == 1):
		if(room_location == "livingroom"):
			json_response = handle_smartthings_request_get("bulb")
			if json_response[1]['value'] == 'off':
				return "Your living room light is already off."
			handle_smartthings_request_put("bulb/off")
			return "I've turned your living room light off."

		elif(room_location == "bedroom"):
			json_response = handle_smartthings_request_get("color")
			if json_response[1]['value'] == 'off':
				return "Your bedroom light is already off."
			handle_smartthings_request_put("color/off")
			return "I've turned your bedroom light off."

		elif(room_location == "both"):
			white_response = handle_smartthings_request_get("bulb")
			color_response = handle_smartthings_request_get("color")
			if white_response[1]['value'] == 'off' and color_response[1]['value'] == 'off':
				return "Your lights are already off."

			handle_smartthings_request_put("bulb/off")
			handle_smartthings_request_put("color/off")
			return "I've turned your lights off."
		else:
			#ambiguous
			return send_room_clarification(input_command, sender_id)

	# LIGHT ON or SWITCH COLOR
	elif(classification_code == 2 or classification_code == 9):
		if(room_location == "livingroom"):
			json_response = handle_smartthings_request_get("bulb")
			if json_response[1]['value'] == 'on':
				return "Your living room light is already on."
			handle_smartthings_request_put("bulb/on")
			return "I've turned your living room light on."

		elif(room_location == "bedroom"):
			color = extract_color(sanitized_command)
			log(color.hsl)
			if(color is None):
				log("not real color")
				handle_smartthings_request_put("color/0/0")
			else:
				log("real color")
				log(int(color.hsl[0]*100))
				handle_smartthings_request_put("color/" + str(int(color.hsl[0]*100)) + "/" + str(int(color.hsl[1]*100)))
			if(classification_code == 9):
				return "I've changed your bedroom light color."
			return "I've turned your bedroom light on."

		elif(room_location == "both"):
			color = extract_color(sanitized_command)
			if(color is None):
				handle_smartthings_request_put("color/0/0")
			else:
				handle_smartthings_request_put("color/" + str(int(color.hsl[0]*100)) + "/" + str(int(color.hsl[1]*100)))
			handle_smartthings_request_put("bulb/on")
			return "I've turned your lights on."

		else: #ambiguous
			return send_room_clarification(input_command, sender_id)

	# DIM LIGHT TODO check state
	elif(classification_code == 3):
		if(room_location == "livingroom"):
			handle_smartthings_request_put("bulb/dim")
			return "Your living room light has been dimmed."

		elif(room_location == "bedroom"):
			handle_smartthings_request_put("color/dim")
			return "Your bedroom light has been dimmed."

		elif(room_location == "both"):
			handle_smartthings_request_put("bulb/dim")
			handle_smartthings_request_put("color/dim")
			return "Your lights have been dimmed."

		else:
			return send_room_clarification(input_command, sender_id)

	# BRIGHTEN LIGHT TODO check state
	elif(classification_code == 4):
		if(room_location == "livingroom"):
			handle_smartthings_request_put("bulb/brighten")
			return "Your living room light has been brightened."

		elif(room_location == "bedroom"):
			handle_smartthings_request_put("color/brighten")
			return "Your bedroom light has been brightened."

		elif(room_location == "both"):
			handle_smartthings_request_put("bulb/brighten")
			handle_smartthings_request_put("color/brighten")
			return "Your lights have been brightened."

		else:
			return send_room_clarification(input_command, sender_id)

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
		json_response = handle_smartthings_request_get("contact")
		#[{u'name': u'status', u'value': [u'closed']}]
		if str(json_response[0]['value']) == "closed":
			return "Your door is closed."
		elif str(json_response[0]['value']) == "open":
			return "Your door is open."
		return "Error, incorrect contact device response."

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
							"title": "Correct response.",
							"payload": "works"
						},
						{
							"type": "postback",
							"title": "Incorrect response.",
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

def update_result(sender_id, success):
	urlparse.uses_netloc.append('postgres')
	url = urlparse.urlparse(os.environ['DATABASE_URL'])
	conn = psycopg2.connect(
		database=url.path[1:],
		user=url.username,
		password=url.password,
		host=url.hostname,
		port=url.port
	)
	query = "SELECT id FROM command_history WHERE client_id = " + str(sender_id) + " ORDER BY write_time DESC LIMIT 1;"
	cur = conn.cursor()
	cur.execute(query)
	record = cur.fetchone()

	query = "UPDATE command_history SET is_correct = " + str(success) + " WHERE id = " + str(record[0]) + ";"
	cur.execute(query)


	conn.commit()
	conn.close()

def extract_location(command):
	'''
	Input: command (string)
	Output: if string refers to living room: "livingroom"
	if string refers to bedroom: "bedroom"
	if string refers to both: "both"
	if string refers to neither: "neither"
	'''
	bothrooms = ["both", "lights", "all"]
	for word in bothrooms:
		if word in command:
			return "both"

	livingroom_on = False
	livingroom = ["livingroom", "den", "family room", "living room", "familyroom", "lounge", "sitting room", "sittingroom"]
	for word in livingroom:
		if word in command:
			livingroom_on = True

	bedroom_on = False
	bedroom = ["bedroom", "bed room", "bed"]
	for word in bedroom:
		if word in command:
			bedroom_on = True

	if livingroom_on and bedroom_on:
		return "both"
	elif livingroom_on:
		return "livingroom"
	elif bedroom_on:
		return "bedroom"
	else:
		return "none"

def party():
    for i in range(0,15):
        h = random.randint(0,100)
        s = random.randint(0,100)
        handle_smartthings_request_put("color/"+str(h)+"/"+str(s))

def extract_color(command):
   for word in command.split():
       try:
           return Color(word)
       except:
           pass
   return None

def send_room_clarification(request_text, sender_id):
    params = {
            "access_token": os.environ["PAGE_ACCESS_TOKEN"]
        }
    headers = {
        "Content-Type": "application/json"
    }
    data = json.dumps({
        "recipient": {
            "id": sender_id
        },
        "message": {
            "attachment": { #comment out the attachment for non-test mode
                "type": "template",
                "payload": {
                    "template_type": "button",
                    "text": "Which light did you mean?",
                    "buttons": [
                        {
                            "type": "postback",
                            "title": "Living room",
                            "payload": request_text + " Living room"
                        },
                        {
                            "type": "postback",
                            "title": "Bedroom",
                            "payload": request_text + " Bedroom"
                        },
                        {
                            "type": "postback",
                            "title": "Both",
                            "payload": request_text + " Bedroom Living room"
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

    return "do not send"

if __name__ == '__main__':
	app.run(debug=True)
