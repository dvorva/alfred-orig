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
import time
import boto
import boto.s3
from boto.s3.key import Key
import base64
import datetime
import random

app = Flask(__name__)

#https://blog.hartleybrody.com/fb-messenger-bot/
#https://alfred-heroku.herokuapp.com/
#https://devcenter.heroku.com/articles/heroku-postgresql    DATABASE_URL
# terminal: heroku pg:psql

@app.route('/contact_sensor_close', methods=['GET'])
def groovy_test():
	#log(request)

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
				"id": 976031225857582
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
								"payload": "do not send"
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


@app.route('/motion_active', methods=['GET'])
def handle_motion_detected_event():
	urlparse.uses_netloc.append('postgres')
	url = urlparse.urlparse(os.environ['DATABASE_URL'])
	conn = psycopg2.connect(
	    database=url.path[1:],
	    user=url.username,
	    password=url.password,
	    host=url.hostname,
	    port=url.port
	)
	query = "UPDATE globals SET value = \'" + str(datetime.datetime.now()) + "\' WHERE key ='last_motion_detected'"
	cur = conn.cursor()
	cur.execute(query)
	conn.commit()
	conn.close()


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
							send_message(sender_id, "Your lights are now off.")
						elif(postback_text == "works"):
							update_result(sender_id, True)
						elif(postback_text == "broken"):
							update_result(sender_id, False)
						else:
							if(postback_text == "do not send"):
								continue
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
	url = "https://graph-na02-useast1.api.smartthings.com:443/api/smartapps/installations/1ab6cf47-df4f-4196-be43-f8e210b3ecde/" + endpoint
	r=requests.get(url, headers={"Authorization":authorization})
	json_data = json.loads(r.text)
	return json_data

def handle_smartthings_request_put(endpoint):
	authorization = "Bearer 4285e326-bb70-47b5-bf2b-02c3462609ae"
	url = "https://graph-na02-useast1.api.smartthings.com:443/api/smartapps/installations/1ab6cf47-df4f-4196-be43-f8e210b3ecde/" + endpoint
	r=requests.put(url, headers={"Authorization":authorization})
	#log(url)

def get_response(input_command, sender_id):

	authorize_check = authorize_user(sender_id)
	if authorize_check == "failure":
		return "You are not authorized to use Alfred."

	input_command = input_command.lower()

	if "party" in input_command:
		party()
		party_reponses = ["No I-I-I-I-I can't stop.", "Hopped off the plane at LAX.", "It's goin' down. I'm yellin' timber!", "Have you ever felt, like a plastic bag?"]
		response = go_blue_reponses[random.randint(1,4)]
		return response

	if "go blue" in input_command:
		wolverine()
		go_blue_reponses = ["I take a pill every day. It's called a steak.", "Who's got it better than us?", "I don't take vacations. I don't get sick. I don't observe major holidays. I'm a jackhammer.", "If you're out of milk, it's OK to substitute Gatorade on your cereal"]
		response = go_blue_reponses[random.randint(1,4)]
		return response

	if "sexy" in input_command or "mood" in input_command:
		sex()
		return ";)"

	# sanitize input
	sanitized_command = sanitize_input(input_command)

	# get result (int)
	classification_code = classify(sanitized_command)

	# log input
	log_message(sender_id, input_command, classification_code)

	# get location of device
	room_location = extract_location(sanitized_command)

	# get user first name:
	name = get_name(sender_id)

	# return response
	if(classification_code == 0):
		return "Sorry, I don't understand."

	# TURN LIGHT OFF
	elif(classification_code == 1):
		if(room_location == "livingroom"):
			json_response = handle_smartthings_request_get("bulb")
			if json_response[1]['value'] == 'off':
				livingroom_light_already_off_reponses = ["Your living room light is off already.", "{0}, your living room light is already off!".format(name), "Looks like your living room light is already off!", "{0}, your living room light is already off!".format(name)]
				response = livingroom_light_already_off_reponses[random.randint(1,4)]
				return response
			handle_smartthings_request_put("bulb/off")
			change_livingroom_light_off_reponses = ["Your living room light is out.", "{0}, your living room light is off.".format(name), "I've switched the living room light off!", "{0}, I've turned your living room light off!".format(name)]
			response = change_bedroom_light_off_reponses[random.randint(1,4)]
			return response

		elif(room_location == "bedroom"):
			json_response = handle_smartthings_request_get("color")
			if json_response[1]['value'] == 'off':
				bedroom_light_already_off_reponses = ["Your bedroom light is off already.", "{0}, your bedroom light is already off!".format(name), "Looks like your bedroom light is already off!", "{0}, your bedroom light is already off!".format(name)]
				response = bedroom_light_already_off_reponses[random.randint(1,4)]
				return response
			handle_smartthings_request_put("color/off")
			change_bedroom_light_off_reponses = ["Your chamber light is now off.", "Hey {0}, your bedroom light is off.".format(name), "Bedroom light is off!", "I've turned your bedroom light off, {0}!".format(name)]
			response = change_bedroom_light_off_reponses[random.randint(1,4)]
			return response

		elif(room_location == "both"):
			white_response = handle_smartthings_request_get("bulb")
			color_response = handle_smartthings_request_get("color")
			if white_response[1]['value'] == 'off' and color_response[1]['value'] == 'off':
				lights_already_off_reponses = ["Your lights are already off.", "{0}, your lights are off.".format(name), "Lights are off!", "{0}, your lights are off!".format(name)]
				response = lights_already_off_reponses[random.randint(1,4)]
				return response

			handle_smartthings_request_put("bulb/off")
			handle_smartthings_request_put("color/off")
			change_lights_off_reponses = ["Lights out!", "{0}, your lights are now off.".format(name), "I've turned your lights off!", "{0}, I've turned your lights off!".format(name)]
			response = change_lights_off_reponses[random.randint(1,4)]
			return response
		else:
			#ambiguous
			return send_room_clarification(input_command, sender_id)

	# LIGHT ON or SWITCH COLOR
	elif(classification_code == 2 or classification_code == 9):
		if(room_location == "livingroom"):
			json_response = handle_smartthings_request_get("bulb")
			if json_response[1]['value'] == 'on':
				livingroom_light_already_on_reponses = ["Your living room light is already on.", "{0}, your living room light is already on.".format(name), "No need, your living room light is already on!", "Hi {0}, your living room light is already on!".format(name)]
				response = livingroom_light_already_on_reponses[random.randint(1,4)]
				return response
			handle_smartthings_request_put("bulb/on")
			change_livingroom_light_on_reponses = ["Your living room light is now on.", "Howdy {0}, your living room bulb is on.".format(name), "I turned on your living room light!", "{0}, I've turned your living room light on!".format(name)]
			response = change_bedroom_light_on_reponses[random.randint(1,4)]
			return response

		elif(room_location == "bedroom"):
			color = extract_color(sanitized_command)
			if(color is None):
				handle_smartthings_request_put("color/0/0")
			else:
				handle_smartthings_request_put("color/" + str(int(color.hsl[0]*100)) + "/" + str(int(color.hsl[1]*100)))
			if(classification_code == 9):
				change_bedroom_light_color_reponses = ["I've changed your bedroom light color, enjoy!", "{0}, your bedroom light color has been changed.".format(name), "I've changed your bedroom light color! Good choice!", "{0}, I've changed your bedroom light color!".format(name)]
				response = change_bedroom_light_color_reponses[random.randint(1,4)]
				return response
			change_bedroom_light_on_reponses = ["Your bedroom light is now on.", "{0}, your bedroom light is on.".format(name), "I turned on your bedroom light!", "{0}, I've turned your bedroom light on!"]
			response = change_bedroom_light_on_reponses[random.randint(1,4)]
			return response

		elif(room_location == "both"):
			color = extract_color(sanitized_command)
			if(color is None):
				handle_smartthings_request_put("color/0/0")
			else:
				handle_smartthings_request_put("color/" + str(int(color.hsl[0]*100)) + "/" + str(int(color.hsl[1]*100)))
			handle_smartthings_request_put("bulb/on")
			change_lights_on_reponses = ["Your lights are now on. You're welcome.", "{0}, your lights are now on.".format(name), "I've turned your lights on!", "{0}, I've turned your lights on!".format(name)]
			response = change_lights_on_reponses[random.randint(1,4)]
			return response

		else: #ambiguous
			return send_room_clarification(input_command, sender_id)

	# DIM LIGHT TODO check state
	elif(classification_code == 3):
		if(room_location == "livingroom"):
			handle_smartthings_request_put("bulb/dim")
			dim_livingroom_light_reponses = ["I've dimmed your living room light.", "{0}, your living room light is now dim.".format(name), "I've set your living room light to dim!", "{0}, I've dimmed your living room light!".format(name)]
			response = dim_livingroom_light_reponses[random.randint(1,4)]
			return response

		elif(room_location == "bedroom"):
			handle_smartthings_request_put("color/dim")
			dim_bedroom_light_reponses = ["I've dimmed your bedroom light.", "{0}, your lights are now dimmed.".format(name), "Your bedroom light is now dim!", "Sure thing, {0}, I just need a ladder, a screwdriver and some electrical tape.".format(name)]
			response = dim_bedroom_light_reponses[random.randint(1,4)]
			return response

		elif(room_location == "both"):
			handle_smartthings_request_put("bulb/dim")
			handle_smartthings_request_put("color/dim")
			dim_lights_reponses = ["I've dimmed your lights.", "{0}, your lights are now set to dim.".format(name), "I've dimmed all your lights!", "{0}, I've dimmed your lights!".format(name)]
			response = dim_lights_reponses[random.randint(1,4)]
			return response

		else:
			return send_room_clarification(input_command, sender_id)

	# BRIGHTEN LIGHT TODO check state
	elif(classification_code == 4):
		if(room_location == "livingroom"):
			handle_smartthings_request_put("bulb/brighten")
			brighten_livingroom_light_reponses = ["Living room light has been brightened!", "{0}, your living room light is now set to bright!".format(name), "I've brightened your living room bulb.", "{0}, I've turned up your living room light brightness!".format(name)]
			response = brighten_livingroom_light_reponses[random.randint(1,4)]
			return response

		elif(room_location == "bedroom"):
			handle_smartthings_request_put("color/brighten")
			brighten_bedroom_light_reponses = ["Sorry, I'm on vacation today. Just kidding - done.", "{0}, your bedroom light is now brightened.".format(name), "I've brightened your bedroom light!", "{0}, I've brightened the bedroom bulb!".format(name)]
			response = brighten_bedroom_light_reponses[random.randint(1,4)]
			return response

		elif(room_location == "both"):
			handle_smartthings_request_put("bulb/brighten")
			handle_smartthings_request_put("color/brighten")
			brighten_lights_reponses = ["Your lights are now brightened! I hope you find what you are looking for!", "{0}, your lights are now brightened.".format(name), "Lights are now set to bright!", "As you wish, Master {0}.".format(name)]
			response = brighten_lights_reponses[random.randint(1,4)]
			return response

		else:
			return send_room_clarification(input_command, sender_id)

	elif(classification_code == 5):
		if(room_location == "livingroom"):
			json_response = handle_smartthings_request_get("bulb")
			if json_response[1]['value'] == 'on':
				livingroom_status_on_reponses = ["Your living room light is on.", "{0}, your living room light is still on.".format(name), "Living room light is on!", "{0}, your living room light is on!".format(name)]
				response = lights_already_on_reponses[random.randint(1,4)]
				return response
			else:
				livingroom_status_off_reponses = ["Don't worry, your living room light is off.", "Your living room light is off, {0}.".format(name), "Living room light is off right now!", "{0}, your living room light is switched off!".format(name)]
				response = lights_already_off_reponses[random.randint(1,4)]
				return response

		elif(room_location == "bedroom"):
			json_response = handle_smartthings_request_get("color")
			if json_response[1]['value'] == 'on':
				bedroom_status_on_reponses = ["Your bedroom light is on.", "{0}, your bedroom light is still on.".format(name), "Bedroom light is on!", "{0}, your bedroom light is on!".format(name)]
				response = lights_already_on_reponses[random.randint(1,4)]
				return response
			else:
				bedroom_status_off_reponses = ["Don't worry, your bedroom light is off.", "Your bedroom light is off, {0}.".format(name), "Bedroom light is off right now!", "{0}, your bedroom light is switched off!".format(name)]
				response = lights_already_off_reponses[random.randint(1,4)]
				return response
		elif(room_location == "both"):
			white_response = handle_smartthings_request_get("bulb")
			color_response = handle_smartthings_request_get("color")
			return_string = ""
			if white_response[1]['value'] == 'on':
				return_string = "Your living room light is on at " + str(white_response[0]['value']) + "%"
			else:
				return_string = "Your living room light is off "
			if color_response[1]['value'] == 'on':
				return_string += " and your bedroom light is on at " + str(color_response[0]['value']) + "%."
			else:
				return_string += " and your bedroom light is off."

			return return_string

		else:
			return send_room_clarification(input_command, sender_id)

	elif(classification_code == 6):
		urlparse.uses_netloc.append('postgres')
		url = urlparse.urlparse(os.environ['DATABASE_URL'])
		conn = psycopg2.connect(
		    database=url.path[1:],
		    user=url.username,
		    password=url.password,
		    host=url.hostname,
		    port=url.port
		)
		query = "SELECT * FROM globals where key = 'last_motion_detected'"
		cur = conn.cursor()
		cur.execute(query)

		record = cur.fetchone()
		log(str(record))

		format = "%Y-%m-%d %H:%M:%S.%f"
		prev_time = datetime.datetime.strptime(record[1], format)
		current_time = datetime.datetime.strptime(str(datetime.datetime.now()), format)

		log(current_time - prev_time)
		delta = current_time - prev_time
		five_minutes = datetime.timedelta(seconds=300)

		conn.commit()
		conn.close()

		if delta < five_minutes:
			return "I detected motion in the last five minutes."
		else:
			return "I have not detected motion recently."

	elif(classification_code == 7):
		send_message(sender_id, "Taking a picture now...")
		json_response = handle_smartthings_request_get("cameraImage")
		upload_jpeg_to_s3(json_response[0]['value'])
		send_picture_message(sender_id)
		image_capture_responses = ["Here's the picture from your camera!", "{0}, here's the image from your camera!".format(name), "Here's your picture!", "{0}, this is the image from your camera!".format(name)]
		response = image_capture_responses[random.randint(1,4)]
		return response

	elif(classification_code == 8):
		json_response = handle_smartthings_request_get("contact")
		#[{u'name': u'status', u'value': [u'closed']}]
		if str(json_response[0]['value']) == "closed":
			door_status_closed_reponses = ["No worries, your door is closed.", "{0}, your door is shut.".format(name), "Your door is currently closed!", "{0}, just checked and your door is closed.".format(name)]
			response = door_status_closed_reponses[random.randint(1,4)]
			return response
		elif str(json_response[0]['value']) == "open":
			door_status_open_reponses = ["Your door is open. That's probably why it's so cold in here!", "{0}, looks like your door is open.".format(name), "Your door is open right now!", "{0}, hurry home, your door is wide open!".format(name)]
			response = door_status_open_reponses[random.randint(1,4)]
			return response
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
		"message":{
			"text": message_text
		}
		#"message": {
		#	"attachment": { #comment out the attachment for non-test mode
		#		"type": "template",
		#		"payload": {
		#			"template_type": "button",
		#			"text": message_text,
		#			"buttons": [
		#				{
		#					"type": "postback",
		#					"title": "Correct response.",
		#					"payload": "works"
		#				},
		#				{
		#					"type": "postback",
		#					"title": "Incorrect response.",
		#					"payload": "broken"
		#				}
		#			]
		#		}
		#	}
		#}
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
					"url":"https://s3.amazonaws.com/alfred-bot/image_capture.jpg"
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

def wolverine():
    handle_smartthings_request_put("color/brighten")
    i = 0
    while(i < 6):
        handle_smartthings_request_put("color/"+str(16)+"/"+str(100))
        time.sleep(1)
        handle_smartthings_request_put("color/"+str(70)+"/"+str(100))
        i+=1

def sex():
    handle_smartthings_request_put("color/"+str(100)+"/"+str(95))
    handle_smartthings_request_put("color/dim")

def extract_color(command):
   for word in command.split():
       try:
           return Color(word)
       except:
           pass
   return None

def get_name(user_id):
	#https://graph.facebook.com/v2.6/<USER_ID>?access_token=PAGE_ACCESS_TOKEN.
	#first_name, last_name, profile_pic, locale, timezone, gender, is_payment_enabled
	urlparse.uses_netloc.append('postgres')
	url = urlparse.urlparse(os.environ['DATABASE_URL'])
	conn = psycopg2.connect(
	    database=url.path[1:],
	    user=url.username,
	    password=url.password,
	    host=url.hostname,
	    port=url.port
	)
	query = "SELECT value FROM globals WHERE key = 'access_token';"
	cur = conn.cursor()
	cur.execute(query)
	record = cur.fetchone()

	#"https://graph.facebook.com/v2.6/<USER_ID>?fields=first_name,last_name,profile_pic,locale,timezone,gender&access_token=PAGE_ACCESS_TOKEN"
	url = "https://graph.facebook.com/v2.6/" + str(user_id) + "?fields=first_name&access_token=" + record[0]
	r = requests.get(url)
	json_data = json.loads(r.text)
	return json_data['first_name']

def authorize_user(requesting_id):
	urlparse.uses_netloc.append('postgres')
	url = urlparse.urlparse(os.environ['DATABASE_URL'])
	conn = psycopg2.connect(
	    database=url.path[1:],
	    user=url.username,
	    password=url.password,
	    host=url.hostname,
	    port=url.port
	)
	query = "SELECT facebook_id FROM user_household WHERE facebook_id = " + str(requesting_id) + ";"
	cur = conn.cursor()
	cur.execute(query)
	if cur.rowcount:
		return "success"
	else:
		return "failure"


# base 64 encoded string (representing image)
def upload_jpeg_to_s3(image_string):
	conn = boto.connect_s3(os.environ['AWS_ACCESS_KEY_ID'], os.environ['AWS_SECRET_ACCESS_KEY'])
	bucket = conn.create_bucket('alfred-bot', location=boto.s3.connection.Location.DEFAULT)
	k = Key(bucket)
	k.set_metadata("Content-Type", "image/jpeg")
	k.key = "image_capture.jpg"
	#k.content_encoding = "base64"
	log(image_string)
	k.set_contents_from_string(base64.b64decode(image_string))
	k.set_acl('public-read')

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
