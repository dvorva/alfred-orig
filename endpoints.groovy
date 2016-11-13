/**
 *  Alfred Endpoints
 *
 *  Copyright 2016 Alfred
 *
 *  Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except
 *  in compliance with the License. You may obtain a copy of the License at:
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 *  Unless required by applicable law or agreed to in writing, software distributed under the License is distributed
 *  on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License
 *  for the specific language governing permissions and limitations under the License.
 *
 */
 
definition(
    name: "Alfred Endpoints",
    namespace: "alfred",
    author: "Alfred",
    description: "Endpoints for Alfred",
    category: "",
    iconUrl: "https://s3.amazonaws.com/smartapp-icons/Convenience/Cat-Convenience.png",
    iconX2Url: "https://s3.amazonaws.com/smartapp-icons/Convenience/Cat-Convenience@2x.png",
    iconX3Url: "https://s3.amazonaws.com/smartapp-icons/Convenience/Cat-Convenience@2x.png",
    oauth: [displayName: "alfred endpoints ", displayLink: "http://localhost:4567"])


preferences {
  /*section ("Samsung Smart Camera - Image Capture") {
    input "cameraImage", "capability.imageCapture", required: true, multiple: false
  }/*
  section ("Samsung Smart Camera - Motion Sensor") {
    input "cameraMotion", "capability.motionSensor", required: true, multiple: false
  }*/
  section ("Philips Hue Color Light.") {
    input "color", "capability.colorControl", required: false, multiple: false
  }
  section ("Fibaro Motion Sensor.") {
    input "contact", "capability.contactSensor", required: false, multiple: false
  }
  section ("Philips Hue White Light.") {
    input "bulb", "capability.switchLevel", required: false, multiple: false
  }
}

mappings {
  path("/cameraMotion") {
    action: [
      GET: "getCameraStatus"
    ]
  }
  path("/cameraImage") {
    action: [
      GET: "takePicture"
    ]
  }
  path("/contact") {
    action: [
      GET: "getContactStatus"
    ]
  }
  path("/bulb") {
    action: [
      GET: "getBulbStatus"
    ]
  }
  path("/bulb/:command") {
    action: [
      PUT: "updateBulb"
    ]
  }
    path("/color") {
    action: [
      GET: "getColorStatus"
    ]
  }
  path("/color/:command") {
    action: [
      PUT: "updateColor"
    ]
  }
  
}

def getBulbStatus() {
    def resp = []
    resp << [name: "level", value: bulb.currentLevel]
    resp << [name: "status", value: bulb.currentSwitch]
    return resp
}

void updateBulb() {
    def command = params.command
    switch(command) {
        case "on":
            bulb.on()
            break
        case "off":
            bulb.off()
            break
        case "brighten":
            bulb.setLevel(100)
            break
        case "dim":
            bulb.setLevel(20)
            break
        default: 
            break
    }
}

def getColorStatus() {
    def resp = []
    resp << [name: "level", value: color.currentLevel]
    resp << [name: "status", value: color.currentSwitch]
    resp << [name: "color", value: color.currentColor]
    return resp
}

void updateColor() {
    def command = params.command
    switch(command) {
        case "on":
            //if(bulb.hasCommand('on')) bulb.on()
            color.on()
            break
        case "off":
            color.off()
            break
        case "brighten":
            color.setLevel(100)
            break
        case "dim":
            color.setLevel(20)
            break
        default:
            //set the color
            color.setSaturation(80)
            color.setHue(command.toInteger())
            color.on()
            break
    }
}

def getContactStatus() {
    def resp = []
    resp << [name: "status", value: contact.currentContact]//contact.currentContact
    return resp
}

def installed() {
    log.debug "Installed with settings: ${settings}"
    initialize()
}

def updated() {
    log.debug "Updated with settings: ${settings}"
    unsubscribe()
    initialize()
}

def initialize() {
    subscribe(contact, "contact.open", openHandler)
    subscribe(contact, "contact.closed", closedHandler)
}

def openHandler(evt) {
    log.debug "$evt.name: $evt.value"
}

def closedHandler(evt) {
    log.debug "$evt.name: $evt.value"
    
    def params = [
        uri: "https://alfred-heroku.herokuapp.com/",
        path: "/test"
    ]

    try {
        httpGet(params) { resp ->
            resp.headers.each {
            log.debug "${it.name} : ${it.value}"
        }
        log.debug "response contentType: ${resp.contentType}"
        log.debug "response data: ${resp.data}"
        }
    } catch (e) {
        log.error "something went wrong: $e"
    }
}



//if(bulb.hasCommand('on')) bulb.on()
/*
def getCameraStatus() {  
    def attrs = cameraMotion.supportedAttributes
    attrs.each {
        log.debug "${cameraMotion.displayName}, attribute ${it.name}, values: ${it.values}"
        log.debug "${cameraMotion.displayName}, attribute ${it.name}, dataType: ${it.dataType}"
    }
}

def takePicture() {
    cameraImage.take()
    def attrs = cameraImage.supportedAttributes
    attrs.each {
        log.debug "${cameraImage.displayName}, attribute ${it.name}, values: ${it.values}"
        log.debug "${cameraImage.displayName}, attribute ${it.name}, dataType: ${it.dataType}"
    }
    //return cameraImage.image
}*/