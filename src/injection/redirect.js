(function() {
    'use strict';

    var REAL_HOSTS = [
        'https://www.handyfeeling.com',
        'https://staging.handyfeeling.com'
    ];

    function extractPath(url) {
        if (typeof url !== 'string') return null;
        for (var i = 0; i < REAL_HOSTS.length; i++) {
            if (url.indexOf(REAL_HOSTS[i]) === 0) {
                return url.substring(REAL_HOSTS[i].length);
            }
        }
        return null;
    }

    function bridgeReady() {
        return !!(window.pywebview && window.pywebview.api && window.pywebview.api.handy_call);
    }

    function callBridge(method, path, body) {
        var bodyStr = null;
        if (body != null) {
            if (typeof body === 'string') bodyStr = body;
            else if (body instanceof ArrayBuffer) bodyStr = new TextDecoder().decode(body);
            else if (body instanceof Blob) bodyStr = null; // fallback, not supported
            else {
                try { bodyStr = JSON.stringify(body); } catch (e) { bodyStr = String(body); }
            }
        }
        return window.pywebview.api.handy_call(method, path, bodyStr);
    }

    // --- Patch fetch() ---
    var _fetch = window.fetch;
    window.fetch = function(input, init) {
        var url, method, body;
        if (typeof input === 'string') {
            url = input;
        } else if (input && typeof input.url === 'string') {
            url = input.url;
        }

        var path = extractPath(url);
        if (!path || !bridgeReady()) {
            return _fetch.call(this, input, init);
        }

        method = (init && init.method) || (input && input.method) || 'GET';
        body = init && init.body;

        console.log('[RestimExt] Bridge fetch: ' + method + ' ' + path);

        return callBridge(method, path, body).then(function(r) {
            var status = (r && r.status) || 200;
            var bodyText = (r && r.body) || '';
            return new Response(bodyText, {
                status: status,
                headers: { 'Content-Type': 'application/json' }
            });
        });
    };

    // --- Patch XMLHttpRequest ---
    var _XhrOpen = XMLHttpRequest.prototype.open;
    var _XhrSend = XMLHttpRequest.prototype.send;
    var _XhrSetRequestHeader = XMLHttpRequest.prototype.setRequestHeader;

    XMLHttpRequest.prototype.open = function(method, url) {
        this.__bridgePath = null;
        var path = extractPath(url);
        if (path) {
            this.__bridgePath = path;
            this.__bridgeMethod = method;
            return; // don't call underlying open — we handle it fully
        }
        return _XhrOpen.apply(this, arguments);
    };

    XMLHttpRequest.prototype.setRequestHeader = function(k, v) {
        if (this.__bridgePath) return; // swallow
        return _XhrSetRequestHeader.apply(this, arguments);
    };

    XMLHttpRequest.prototype.send = function(body) {
        var self = this;
        if (!self.__bridgePath) return _XhrSend.apply(self, arguments);
        if (!bridgeReady()) {
            console.warn('[RestimExt] XHR bridge not ready, aborting');
            return;
        }
        console.log('[RestimExt] Bridge XHR: ' + self.__bridgeMethod + ' ' + self.__bridgePath);
        callBridge(self.__bridgeMethod, self.__bridgePath, body).then(function(r) {
            var status = (r && r.status) || 200;
            var bodyText = (r && r.body) || '';
            try {
                Object.defineProperty(self, 'readyState', { value: 4, configurable: true });
                Object.defineProperty(self, 'status', { value: status, configurable: true });
                Object.defineProperty(self, 'statusText', { value: 'OK', configurable: true });
                Object.defineProperty(self, 'responseText', { value: bodyText, configurable: true });
                Object.defineProperty(self, 'response', { value: bodyText, configurable: true });
            } catch (e) {}
            try { if (typeof self.onreadystatechange === 'function') self.onreadystatechange(); } catch (e) {}
            try { if (typeof self.onload === 'function') self.onload(); } catch (e) {}
            try { self.dispatchEvent(new Event('readystatechange')); } catch (e) {}
            try { self.dispatchEvent(new Event('load')); } catch (e) {}
            try { self.dispatchEvent(new Event('loadend')); } catch (e) {}
        });
    };

    console.log('[RestimExt] Handy API bridge installed (via pywebview.api)');
})();
