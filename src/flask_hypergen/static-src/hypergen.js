import morphdom from 'morphdom'
import './hypergen'
import * as hypergen from './hypergen'
import * as websocket from './websocket';

// Make all exported vars availabe inside window.hypergen.
window.hypergen = hypergen
window.hypergen.websocket = websocket

// Shims
if (typeof Array.isArray === 'undefined') {
  Array.isArray = function(obj) {
    return Object.prototype.toString.call(obj) === '[object Array]';
  }
}

// Commands that can be called from the backend.
export const morph = function(id, html, autofocus=true) {
  const element = document.getElementById(id)
  if (!element) {
    console.error("Trying to morph into an element with id='" + id + "' that does not exist. Please check your target_id.")
    return
  }
  morphdom(
    element,
    typeof html === "string" ? "<div>" + html + "</div>" : html,
    {
      childrenOnly: true,
      onBeforeElUpdated: function(fromEl, toEl) {
        let focused = document.activeElement
        if((fromEl.nodeName == "INPUT" || fromEl.nodeName == "TEXTAREA") && fromEl === focused) {
          let types = ["checkbox", "radio"]
          if (fromEl.nodeName === "INPUT" && types.indexOf(fromEl.type) !== -1) {
            return true
          }
          mergeAttrs(fromEl, toEl)
          return false
        } else if (fromEl.nodeName == "INPUT" && fromEl.type === "file" && fromEl.files.length > 0) {
          mergeAttrs(fromEl, toEl)
          return false
        } else if (fromEl.nodeName === "SCRIPT" && toEl.nodeName === "SCRIPT") {
            var script = document.createElement('script');
            //copy over the attributes
            [...toEl.attributes].forEach( attr => { script.setAttribute(attr.nodeName ,attr.nodeValue) })
            script.innerHTML = toEl.innerHTML;
            fromEl.replaceWith(script)
            return false;
        } else {
          return true
        }
      },
      onNodeAdded: function (node) {
        if (node.nodeName === 'SCRIPT') {
          var script = document.createElement('script');
          //copy over the attributes
          [...node.attributes].forEach( attr => { script.setAttribute(attr.nodeName ,attr.nodeValue) })
          script.innerHTML = node.innerHTML;
          node.replaceWith(script)
        }
      },
    }
  )

  if (autofocus) {
    const autofocusElement = document.querySelectorAll('[autofocus]')[0]
    if (autofocusElement !== undefined) autofocusElement.focus()
  }
}

export const remove = function(id) {
  let el = document.getElementById(id);
  if (!!el) el.parentNode.removeChild(el)
}

export const hide = function(id) {
  let el = document.getElementById(id)
  el.style.display = "none"
}

export const display = function(id, value) {
  let el = document.getElementById(id)
  el.style.display = value || "block"
}

export const visible = function(id, value) {
  let el = document.getElementById(id)
  el.style.visibility = "visible"
}

export const hidden = function(id, value) {
  let el = document.getElementById(id)
  el.style.visibility = "hidden"
}

export const redirect = function(url) {
  /*
  One would expect to simply do a window.location = url but that does not work in an ajax request on safari, because
  (i think) the ajax request is async and the redirect is thus triggered directly during a user event.
  This is a workaround, but might stop working some day.
  */
  const link = document.createElement('a')
  link.href = url
  link.style.display = 'none'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

export const append = function(id, html) {
  const el = document.getElementById(id)
  if (!el) console.error("Cannot append to missing element", id)
  el.innerHTML += html
}

export const prepend = function(id, html) {
  const el = document.getElementById(id)
  if (!el) console.error("Cannot prepend to missing element", id)
  el.innerHTML = html + el.innerHTML
}

hypergen.clientState = {}

export const setClientState = function(at, value) {
  let clientState = hypergen.clientState
  for (const path of at.split(".")) {
    if (clientState[path] === undefined) clientState[path] = {}
    clientState = clientState[path]
  }
  Object.assign(clientState, value)
  console.log("Setting new state for hypergen.clientState", at, "with value", value, "giving",
              hypergen.clientState)
}

/* WARNING NOT STABLE */
var INTERVALS = {}

export const intervalSet = function(commands, interval, name) {
  const i = setInterval(() => applyCommands(commands), interval)
  if (!!name) INTERVALS[name] = i
}

export const intervalClear = function(name) {
  if (INTERVALS[name]) {
    console.log("Clearing", INTERVALS[name])
    clearInterval(INTERVALS[name])
  }
}

export const addEventListener = function(querySelectorString, type, commands, options) {
  document.querySelector(querySelectorString).addEventListener(
    type, (event) => applyCommands(commands), options || {})
}

let _TTT = {}

const keypressToCallbackFunc = function(e) {
  const [url, args, options] = _TTT
  callback(url, [e.key, ...(args || [])], options || {})
}
export const keypressToCallback = function(url, args, options) {
  _TTT = [url, args, options]
  window.addEventListener("keydown", keypressToCallbackFunc)
}
export const keypressToCallbackRemove = function(url, args, options) {
  window.removeEventListener("keydown", keypressToCallbackFunc)
}
/* END WARNING STABLE AGAIN */

// Callback
var i = 0
var isBlocked = false
var urlBlocks = {}
export const callback = function(url, args, {debounce=0, confirm_=false, blocks=false, blocksEachUrl=true, uploadFiles=false,
                                             params={}, meta={}, clear=false, elementId=null, debug=false,
                                             event=null, headers={}, onSucces=null, timeout=20000}={}, ) {

  const isWebsocket = (url.startsWith("ws://") || url.startsWith("wss://"))

  if (!!event) {
    event.preventDefault()
    event.stopPropagation()
  }

  let postIt = function() {
    let json
    console.log("REQUEST", url, args, debounce)
    i++

    // The element function must have access to the FormData.
    hypergen.hypergenGlobalFormdata = new FormData()
    hypergen.hypergenUploadFiles = uploadFiles
    try {
      json = JSON.stringify({
        args: args,
        meta: meta,
      })
    } catch(error) {
      if (error === MISSING_ELEMENT_EXCEPTION) {
        console.warn("An element is missing. This can happen if a dom element has multiple event handlers.", url)
        return
      } else {
        throw(error)
      }
    }


    let formData = hypergen.hypergenGlobalFormdata
    hypergen.hypergenGlobalFormdata = null
    hypergen.hypergenUploadFiles = null
    formData.append("hypergen_data", json)

    if (blocks === true) {
      if (isBlocked === true) {
        console.error("Callback was blocked")
        return
      } else {
        isBlocked = true
      }
    }

    if (blocksEachUrl === true && !isWebsocket) {
      if (!!urlBlocks[url]) {
        console.error("Callback to " + url + " was blocked")
        return
      }

      urlBlocks[url] = true
    }

    post(url, formData, (data) => {
      if (data !== null) applyCommands(data)
      isBlocked = false
      if (blocksEachUrl === true && !isWebsocket) {
        delete urlBlocks[url]
      }
      if (clear === true) document.getElementById(elementId).value = ""
      if (!!onSucces) onSucces()
    }, (data, jsonOk, xhr) => {
      console.log("xhr:", xhr)
      isBlocked = false
      if (blocksEachUrl === true && !isWebsocket) {
        delete urlBlocks[url]
      }
      console.error("Hypergen post error occured", data)
      if (debug !== true) {
        if (xhr.getResponseHeader("Content-Type") === "text/plain") {
          data = "<pre><code>" + data + "</pre></code>"
        }
        document.getElementsByTagName("html")[0].innerHTML = data
      }
    }, params, headers, {timeout})
  }
  const postItWebsocket = function() {
    console.log("WEBSOCKET", url, args, debounce)
    let json
    try {
      json = JSON.stringify({
        args: args,
        meta: meta,
      })
    } catch(error) {
      if (error === MISSING_ELEMENT_EXCEPTION) {
        console.warn("An element is missing. This can happen if a dom element has multiple event handlers.", url)
        return
      } else {
        throw(error)
      }
    }
    if (!hypergen.websocket.WEBSOCKETS[url]) {
      console.error("Cannot send WS to non existing connection:", url)
      return
    }
    hypergen.websocket.WEBSOCKETS[url].send(json)
    if (clear === true) document.getElementById(elementId).value = ""

  }

  const func = isWebsocket ? postItWebsocket : postIt

  if (debounce === 0) {
    if (confirm_ === false) func()
    else if (confirm(confirm_)) func()
  }
  else throttle(func, {delay: debounce, group: url, confirm_})
}

export const partialLoad = function(event, url, pushState) {
  console.log("partialLoad to", url, pushState)
  window.dispatchEvent(new CustomEvent('hypergen.partialLoad.before', {detail: {event, url, pushState}}))
  callback(url, [], {'event': event, 'headers': {'X-Hypergen-Partial': '1'}, onSucces: function() {
    if (!!pushState) {
      console.log("pushing state!")
      history.pushState({callback_url: url}, "", url)
      onpushstate()
      history.forward()
      window.dispatchEvent(new CustomEvent('hypergen.partialLoad.after', {detail: {event, url, pushState}}))
    }
  }})
}

// Timing
var _THROTTLE_GROUPS = {}
export let throttle = function (func, {delay=0, group='global', confirm_=false}={}) {
  if (_THROTTLE_GROUPS[group]) {
    clearTimeout(_THROTTLE_GROUPS[group])
    _THROTTLE_GROUPS[group] = null
  }

  _THROTTLE_GROUPS[group] = setTimeout(function () {
      if (confirm_ === false) {
        func()
      } else {
        const confirmed = confirm(confirm_)
        if (confirmed === true) {
          func()
        }
      }
      _THROTTLE_GROUPS[group] = null
    }, delay)
}

export let cancelThrottle = function(group) {
  if (_THROTTLE_GROUPS[group]) {
    clearTimeout(_THROTTLE_GROUPS[group])
    _THROTTLE_GROUPS[group] = null
  }
}

// Internal

const require_ = function(module) {
  try {
    return require(module)
  } catch(e) {
    return false
  }
}

const resolvePath = function(path) {
  const parts = path.split(".")
  let i = -1, obj = null
  for (let part of parts) {
    i++
    if (i === 0) {
      if (window[part] !== undefined) obj = window[part]
      else if (obj = require_(part)) null
      else if (obj = require_("./" + part)) null
      else throw "Could not resolve path: " + path
    } else {
      if (obj[part] !== undefined) {
        try {
          obj = obj[part].bind(obj)
        } catch(e) {
          obj = obj[part]
        }
      }
      else throw "Could not resolve path: " + path
    }
  }
  return obj
}

const applyCommand = function(path, ...args) {
  console.log("apply command", path, args)
  let rpath = resolvePath(path)
  const result = rpath(...args)
  const event = new CustomEvent('hypergen.applyCommand.after', {detail: {path, args}})
  document.dispatchEvent(event)
  return result
}

export const event = function(event, callbackKey, when) {
  event.preventDefault()
  event.stopPropagation()
  if (!!when && !applyCommand(...when, event)) return
  applyCommand(...hypergen.clientState.hypergen.eventHandlerCallbacks[callbackKey])
}

export const applyCommands = function(commands) {
  if (!!commands._ && commands._.length === 2 && commands._[0] === "deque") {
    commands = commands._[1]
  }
  for (let [path, ...args] of commands) {
    applyCommand(path, ...args)
  }
}

const mergeAttrs = function(target, source){
  source.getAttributeNames().forEach(name => {
    let value = source.getAttribute(name)
    target.setAttribute(name, value)
  })
}

const callbackIdsIn = function(boundary) {
  const ids = new Set()
  const elements = [boundary, ...boundary.querySelectorAll('*')]
  const pattern = /hypergen\.event\s*\(\s*event\s*,\s*(['"])(.*?)\1/g

  for (const element of elements) {
    for (const attribute of element.attributes) {
      pattern.lastIndex = 0
      for (
        let match = pattern.exec(attribute.value);
        match;
        match = pattern.exec(attribute.value)
      ) {
        ids.add(match[2])
      }
    }
  }
  return ids
}

const parseBoundary = function(update, existing) {
  const range = document.createRange()
  range.selectNode(existing)
  const fragment = range.createContextualFragment(update.html)
  const elements = [...fragment.children]
  const nonWhitespaceText = [...fragment.childNodes].some(
    node => node.nodeType === Node.TEXT_NODE && node.textContent.trim() !== '',
  )
  const boundaries = fragment.querySelectorAll('[data-hypergen-region]')

  if (
    elements.length !== 1 ||
    nonWhitespaceText ||
    boundaries.length !== 1 ||
    !elements[0].hasAttribute('data-hypergen-region')
  ) {
    throw new Error(
      `Returned update for region "${update.region}" must contain exactly one region boundary.`,
    )
  }

  const returned = elements[0]
  const returnedName = returned.getAttribute('data-hypergen-region')
  if (returnedName !== update.region) {
    throw new Error(
      `Returned region "${returnedName}" does not match update "${update.region}".`,
    )
  }
  if (returned.localName !== existing.localName) {
    throw new Error(
      `Returned region "${update.region}" must use <${existing.localName}>, not <${returned.localName}>.`,
    )
  }
  // Keep scripts inert until morphdom's existing onNodeAdded hook executes them once.
  // Parsing their children again on the boundary itself preserves restricted contexts.
  returned.innerHTML = returned.innerHTML
  return returned
}

const parseMainUpdate = function(update, existing) {
  if (update.swap !== 'inner-morph') {
    throw new Error(`Unsupported main target swap: ${update.swap}`)
  }
  const range = document.createRange()
  range.selectNode(existing)
  const returned = existing.cloneNode(false)
  const fragment = range.createContextualFragment(update.html)
  returned.appendChild(fragment)
  returned.innerHTML = returned.innerHTML
  return returned
}

let temporaryRegionId = 0

const morphBoundary = function(existing, returned) {
  const hadId = existing.hasAttribute('id')
  const originalId = existing.getAttribute('id')
  let id = originalId
  if (!id || document.getElementById(id) !== existing) {
    do {
      temporaryRegionId += 1
      id = `hypergen-region-update-${temporaryRegionId}`
    } while (document.getElementById(id))
    existing.setAttribute('id', id)
  }

  try {
    morph(id, returned, false)
  } finally {
    if (hadId) {
      existing.setAttribute('id', originalId)
    } else {
      existing.removeAttribute('id')
    }
  }
}

export const applyUpdates = function(
  updates,
  eventHandlerCallbacks=null,
  mainUpdate=null,
  callbackTargetId=null,
) {
  const existingByName = new Map()
  for (const boundary of document.querySelectorAll('[data-hypergen-region]')) {
    const name = boundary.getAttribute('data-hypergen-region')
    const matches = existingByName.get(name) || []
    matches.push(boundary)
    existingByName.set(name, matches)
  }

  const requested = new Set()
  const prepared = updates.map(update => {
    const matches = existingByName.get(update.region) || []
    if (matches.length !== 1) {
      throw new Error(`Hypergen region "${update.region}" must exist exactly once.`)
    }
    if (requested.has(update.region)) {
      throw new Error(`Hypergen region "${update.region}" may only be updated once per batch.`)
    }
    requested.add(update.region)
    if (update.swap !== 'inner-morph') {
      throw new Error(`Unsupported region swap: ${update.swap}`)
    }
    return {
      existing: matches[0],
      returned: parseBoundary(update, matches[0]),
      update,
    }
  })

  let preparedMain = null
  if (mainUpdate) {
    const matches = [...document.querySelectorAll('[id]')].filter(
      element => element.getAttribute('id') === mainUpdate.target,
    )
    if (matches.length !== 1) {
      throw new Error(
        `Hypergen main target "${mainUpdate.target}" must exist exactly once.`,
      )
    }
    preparedMain = {
      existing: matches[0],
      returned: parseMainUpdate(mainUpdate, matches[0]),
      update: mainUpdate,
    }
  }

  const preparedTargets = prepared.map(item => ({
    existing: item.existing,
    label: item.update.region,
  }))
  if (preparedMain) {
    preparedTargets.push({
      existing: preparedMain.existing,
      label: `main target ${preparedMain.update.target}`,
    })
  }
  for (let i = 0; i < preparedTargets.length; i += 1) {
    for (let j = i + 1; j < preparedTargets.length; j += 1) {
      const first = preparedTargets[i]
      const second = preparedTargets[j]
      let ancestor = null
      let descendant = null
      if (first.existing.contains(second.existing)) {
        ancestor = first
        descendant = second
      } else if (second.existing.contains(first.existing)) {
        ancestor = second
        descendant = first
      }
      if (ancestor) {
        throw new Error(
          `Hypergen update targets "${ancestor.label}" and "${descendant.label}" ` +
            'must not overlap.',
        )
      }
    }
  }

  document.dispatchEvent(
    new CustomEvent('hypergen.applyUpdates.before', {detail: {updates, mainUpdate}}),
  )

  const clientState = hypergen.clientState
  if (!clientState.hypergen) clientState.hypergen = {}
  if (!clientState.hypergen.eventHandlerCallbacks) {
    clientState.hypergen.eventHandlerCallbacks = {}
  }
  const callbacks = clientState.hypergen.eventHandlerCallbacks
  const callbackBoundaries = prepared.map(item => item.existing)
  if (preparedMain) callbackBoundaries.push(preparedMain.existing)
  if (callbackTargetId) {
    const callbackTarget = document.getElementById(callbackTargetId)
    if (callbackTarget) callbackBoundaries.push(callbackTarget)
  }
  for (const boundary of callbackBoundaries) {
    for (const callbackId of callbackIdsIn(boundary)) delete callbacks[callbackId]
  }
  if (eventHandlerCallbacks) Object.assign(callbacks, eventHandlerCallbacks)

  for (const {existing, returned, update} of prepared) {
    document.dispatchEvent(
      new CustomEvent('hypergen.applyUpdate.before', {detail: {update, boundary: existing}}),
    )
    morphBoundary(existing, returned)
    document.dispatchEvent(
      new CustomEvent('hypergen.applyUpdate.after', {detail: {update, boundary: existing}}),
    )
  }

  if (preparedMain) {
    document.dispatchEvent(
      new CustomEvent('hypergen.applyUpdate.before', {
        detail: {update: preparedMain.update, boundary: preparedMain.existing},
      }),
    )
    morphBoundary(preparedMain.existing, preparedMain.returned)
    document.dispatchEvent(
      new CustomEvent('hypergen.applyUpdate.after', {
        detail: {update: preparedMain.update, boundary: preparedMain.existing},
      }),
    )
  }

  if (prepared.length || preparedMain) {
    const autofocus = document.querySelector('[autofocus]')
    if (autofocus) autofocus.focus()
  }
  document.dispatchEvent(
    new CustomEvent('hypergen.applyUpdates.after', {detail: {updates, mainUpdate}}),
  )
}

const navigationState = function(url) {
  return {hypergen_url: new URL(url, window.location.href).href}
}

const normalizeCurrentNavigationState = function() {
  if (history.state && history.state.hypergen_url) return
  const state = Object.assign({}, history.state, navigationState(window.location.href))
  delete state.callback_url
  history.replaceState(state, '', window.location.href)
}

let navigationGeneration = 0

export const navigate = async function(event, url, historyMode='push') {
  if (event) {
    event.preventDefault()
    event.stopPropagation()
  }
  if (!['push', 'replace', 'none'].includes(historyMode)) {
    throw new Error(`Unsupported history mode: ${historyMode}`)
  }

  const resolvedUrl = new URL(url, window.location.href).href
  const generation = ++navigationGeneration
  window.dispatchEvent(
    new CustomEvent('hypergen.navigate.before', {
      detail: {event, url: resolvedUrl, history: historyMode},
    }),
  )

  let response
  try {
    response = await fetch(resolvedUrl, {
      method: 'GET',
      credentials: 'same-origin',
      headers: {
        'X-Hypergen-Partial': '1',
        'X-Requested-With': 'XMLHttpRequest',
        'X-Pathname': window.location.pathname,
      },
    })
  } catch (error) {
    if (generation !== navigationGeneration) return
    throw error
  }
  if (generation !== navigationGeneration) return
  if (!response.ok && response.status !== 302) {
    throw new Error(`Hypergen navigation failed with status ${response.status}.`)
  }

  const text = await response.text()
  if (generation !== navigationGeneration) return
  const commands = JSON.parse(text, reviver)
  if (generation !== navigationGeneration) return

  applyCommands(commands)
  if (historyMode === 'push') {
    normalizeCurrentNavigationState()
    history.pushState(navigationState(resolvedUrl), '', resolvedUrl)
  } else if (historyMode === 'replace') {
    history.replaceState(navigationState(resolvedUrl), '', resolvedUrl)
  }
  onpushstate()
  window.dispatchEvent(
    new CustomEvent('hypergen.navigate.after', {
      detail: {event, url: resolvedUrl, history: historyMode},
    }),
  )
}

const MISSING_ELEMENT_EXCEPTION = "MISSING_ELEMENT_EXCEPTION"

// coerce functions
export const coerce = {}
coerce.no = function(value) {
  if (value === "") return null
  return value
}
coerce.str = function(value) {
  if (value === "") return null
  return value === null ? null : "" + value
}
coerce.int = function(value) {
  if (value === "") return null
  value = parseInt(value)
  if (isNaN(value)) return null
  else return value
}
coerce.intlist = function(value) {
  return value.map(x => parseInt(x))
}
coerce.float = function(value) {
  if (value === "") return null
  value = parseFloat(value)
  if (isNaN(value)) return null
  else return {_: ["float", value]}
}
coerce.date = function(value) {
  if (value === "") return null
  else return {_: ["date", value]}
}
coerce.datetime = function(value) {
  if (value === "") return null
  else return {_: ["datetime", value]}
}
coerce.time = function(value) {
  if (value === "") return null
  else return {_: ["time", value]}
}
coerce.month = function(value) {
  if (value === "") return null
  const parts = value.split("-")
  return {year: parseInt(parts[0]), month: parseInt(parts[1])}
}
coerce.week = function(value) {
  if (value === "") return null
  const parts = value.split("-")
  return {year: parseInt(parts[0]), week: parseInt(parts[1].replace("W", ""))}
}


// DOM element value readers
export const read = {}
read.value = function(id) { // value attribute
  const el = document.getElementById(id)
  if (el === null) {
    throw MISSING_ELEMENT_EXCEPTION
  }
  return el.value.trim()
}
read.checked = function(id) { // checkbox
  const el = document.getElementById(id)
  if (el === null) {
    throw MISSING_ELEMENT_EXCEPTION
  }
  return el.checked
}
read.radio = function(id) { // radio button. Uses name attribute for value.
  const el = document.getElementById(id)
  if (el === null) {
    throw MISSING_ELEMENT_EXCEPTION
  }
  const checked = document.querySelector("input[type=radio][name=" + el.name + "]:checked")
  return checked === null ? null : checked.value
}
read.contenteditable = function(id) { // contenteditable attribute enabled
  const el = document.getElementById(id)
  if (el === null) {
    throw MISSING_ELEMENT_EXCEPTION
  }
  return el.innerHTML
}
read.selectMultiple = function(id) { // select, multiple support
  const el = document.getElementById(id)
  if (el === null) {
    throw MISSING_ELEMENT_EXCEPTION
  }
  return Array.from(el.selectedOptions).map(option => option.value)
}
read.file = function(id, formData) { // file upload
  const el = document.getElementById(id)
  if (el === null) {
    throw MISSING_ELEMENT_EXCEPTION
  }
  if (el.files.length !== 1) return null
  if (hypergen.hypergenUploadFiles === true) formData.append(id, el.files[0])
  return el.files[0].name
}

// When functions
export const when = {}
when.keycode = function(keycode, event) {
  return event.code == keycode
}

export const element = function(valueFunc, coerceFunc, id) {
  this.toJSON = function() {
    const value = resolvePath(valueFunc)(id, hypergen.hypergenGlobalFormdata)
    if (!!coerceFunc) return resolvePath(coerceFunc)(value)
    else return coerce.no(value)
  }
  return this
}

export const reviver = function(k, v) {
  if (Array.isArray(v)) {
    if (v.length === 3 && v[0] === "_") {
      if(v[1] === "element_value") {
        return new element(...v[2])
      }
    }
  }
  return v
}

const getCookie = function(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

function addParams(url, params) {
  const ret = []
  for (let d in params)
    ret.push(encodeURIComponent(d) + '=' + encodeURIComponent(params[d]))
  if (ret.length === 0) return url
  else return url + "?" + ret.join('&')
}

const post = function(url, formData, onSuccess, onError, params, headers, {timeout=20000}={}) {
  url = addParams(url, params)

  const xhr = new XMLHttpRequest()
  xhr.timeout = timeout

  const progressBar = document.getElementById("hypergen-upload-progress-bar")

  if (progressBar !== null) {
    xhr.upload.onload = () => {
      progressBar.style.visibility = "hidden"
      console.log(`The upload is completed: ${xhr.status} ${xhr.response}`)
    }

    xhr.upload.onerror = () => {
      progressBar.style.visibility = "hidden"
      console.error('Upload failed.')

    }

    xhr.upload.onabort = () => {
      progressBar.style.visibility = "hidden"
      console.error('Upload cancelled.')
    }

    xhr.upload.onprogress = (event) => {
      progressBar.style.visibility = "visible"
      progressBar.value = event.loaded / event.total
      console.log(`Uploaded ${event.loaded} of ${event.total} bytes`)
    }
  }

  xhr.onload = () => {
    var jsonOk = false,
        data = null
    try {
      data = JSON.parse(xhr.responseText, reviver)
      jsonOk = true
    } catch(e) {
      data = xhr.responseText
      jsonOk = false
    }
    if (xhr.readyState == 4 && (xhr.status == 200 || xhr.status == 302)) {
      window.dispatchEvent(new CustomEvent('hypergen.post.after'))
      onSuccess(data, xhr)
    } else {
      window.dispatchEvent(new CustomEvent('hypergen.post.after'))
      onError(data, jsonOk, xhr);
    }
  }

  xhr.onerror = () => {
    console.error('xhr onerror')
    window.dispatchEvent(new CustomEvent('hypergen.post.after'))
    onError()
  }

  xhr.onabort = () => {
    console.error('xhr onabort')
    window.dispatchEvent(new CustomEvent('hypergen.post.after'))
    onError()
  }

  xhr.ontimeout = () => {
    console.error('xhr ontimeout')
    window.dispatchEvent(new CustomEvent('hypergen.post.after'))
    onError()
  }

  xhr.open('POST', url)
  xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
  xhr.setRequestHeader('X-Pathname', parent.window.location.pathname);
  xhr.setRequestHeader('X-CSRFToken', getCookie('csrftoken'));
  if (!!headers) {
    for (let k in headers) {
      console.log("Setting custom header", k, "to", headers[k])
      xhr.setRequestHeader(k, headers[k]);
    }
  }
  window.dispatchEvent(new CustomEvent('hypergen.post.before'))
  xhr.send(formData)
}

// history support.

window.addEventListener("popstate", function(event) {
  if (event.state && event.state.callback_url !== undefined) {
    console.log("popstate to partial load")
    partialLoad(event, event.state.callback_url)
  } else {
    window.location = location.href
  }
})

window.addEventListener(
  'popstate',
  function(event) {
    if (!event.state || !event.state.hypergen_url) return
    event.stopImmediatePropagation()
    navigate(event, event.state.hypergen_url, 'none')
  },
  {capture: true},
)

const pushstate = new Event('hypergen.pushstate')

export const onpushstate = function() {
  document.dispatchEvent(pushstate)
}

// On ready

export const ready = function(fn, {partial=false}={}) {
  if (document.readyState != 'loading') {
    fn();
  } else if (document.addEventListener) {
    document.addEventListener('DOMContentLoaded', fn);
  } else {
    document.attachEvent('onreadystatechange', function() {
      if (document.readyState != 'loading')
        fn();
    });
  }
  if (partial) document.addEventListener("hypergen.pushstate", fn)
}
