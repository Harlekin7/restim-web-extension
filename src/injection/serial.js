(function() {
    'use strict';

    if (window.__restimSerialPatched) return;
    window.__restimSerialPatched = true;

    function forward(text) {
        if (!text) return;
        if (!window.pywebview || !window.pywebview.api || !window.pywebview.api.tcode_write) {
            console.warn('[RestimExt] write() but pywebview bridge not ready');
            return;
        }
        try { window.pywebview.api.tcode_write(text); } catch (e) {
            console.error('[RestimExt] tcode_write failed', e);
        }
    }

    function makeFakePort() {
        var decoder = new TextDecoder('utf-8', { fatal: false });
        var encoder = new TextEncoder();

        // Writable: browser → device  (we capture and forward to Python)
        var writable = new WritableStream({
            write: function(chunk) {
                try {
                    var text;
                    if (chunk instanceof Uint8Array) {
                        text = decoder.decode(chunk, { stream: true });
                    } else if (chunk instanceof ArrayBuffer) {
                        text = decoder.decode(new Uint8Array(chunk), { stream: true });
                    } else {
                        text = String(chunk);
                    }
                    console.log('[RestimExt] serial write:', JSON.stringify(text));
                    forward(text);
                } catch (e) {
                    console.error('[RestimExt] write error', e);
                }
            },
            close: function() { console.log('[RestimExt] writable close'); },
            abort: function(reason) { console.log('[RestimExt] writable abort', reason); }
        });

        // Readable: device → browser  (we emit a TCode greeting so the host
        // accepts the device as a valid TCode v0.3 endpoint)
        var readableController = null;
        var pendingGreeting = null;

        var readable = new ReadableStream({
            start: function(controller) {
                readableController = controller;
                if (pendingGreeting) {
                    try { controller.enqueue(encoder.encode(pendingGreeting)); } catch (e) {}
                    pendingGreeting = null;
                }
            }
        });

        function emitLine(text) {
            var line = text.endsWith('\n') ? text : (text + '\n');
            if (readableController) {
                try { readableController.enqueue(encoder.encode(line)); } catch (e) {}
            } else {
                pendingGreeting = line;
            }
        }

        var port = {
            open: function(options) {
                console.log('[RestimExt] fakeSerial.open', options);
                // Emit TCode v0.3 greeting — most host tools listen for this
                // on port open to confirm a compatible device.
                setTimeout(function() {
                    emitLine('TCode v0.3 RestimExt');
                    emitLine('D1 RestimExt');
                    emitLine('D2 v0.3.0');
                }, 50);
                return Promise.resolve();
            },
            close: function() {
                console.log('[RestimExt] fakeSerial.close');
                return Promise.resolve();
            },
            writable: writable,
            readable: readable,
            getInfo: function() {
                return { usbVendorId: 0xCAFE, usbProductId: 0xBABE };
            },
            getSignals: function() {
                return Promise.resolve({
                    dataCarrierDetect: false,
                    clearToSend: true,
                    ringIndicator: false,
                    dataSetReady: true
                });
            },
            setSignals: function() { return Promise.resolve(); },
            forget: function() { return Promise.resolve(); }
        };

        var listeners = {};
        port.addEventListener = function(type, cb) {
            (listeners[type] = listeners[type] || []).push(cb);
        };
        port.removeEventListener = function(type, cb) {
            if (!listeners[type]) return;
            listeners[type] = listeners[type].filter(function(x) { return x !== cb; });
        };
        port.dispatchEvent = function() { return true; };

        return port;
    }

    var fakePort = makeFakePort();

    var fakeSerial = {
        requestPort: function(options) {
            console.log('[RestimExt] navigator.serial.requestPort', options);
            return Promise.resolve(fakePort);
        },
        getPorts: function() {
            return Promise.resolve([fakePort]);
        },
        addEventListener: function() {},
        removeEventListener: function() {},
        dispatchEvent: function() { return true; }
    };

    try {
        Object.defineProperty(navigator, 'serial', {
            value: fakeSerial,
            configurable: true,
            writable: false
        });
    } catch (e) {
        try { navigator.serial = fakeSerial; } catch (e2) {}
    }

    console.log('[RestimExt] navigator.serial patched (fake T-Code port)');
})();
