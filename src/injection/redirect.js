(function() {
    'use strict';

    var FAKE_API = 'http://{{HOST}}:{{PORT}}/api/handy/v2';

    var REAL_APIS = [
        'https://www.handyfeeling.com/api/handy/v2',
        'https://www.handyfeeling.com/api/handy-rest/v2',
        'https://staging.handyfeeling.com/api/handy/v2'
    ];

    function redirectUrl(url) {
        for (var i = 0; i < REAL_APIS.length; i++) {
            if (url.indexOf(REAL_APIS[i]) === 0) {
                var redirected = url.replace(REAL_APIS[i], FAKE_API);
                console.log('[RestimExt] Redirect: ' + url + ' -> ' + redirected);
                return redirected;
            }
        }
        return null;
    }

    // --- Patch fetch() ---
    var _fetch = window.fetch;
    window.fetch = function(input, init) {
        var url;
        if (typeof input === 'string') {
            url = redirectUrl(input);
            if (url) input = url;
        } else if (input && input instanceof Request) {
            url = redirectUrl(input.url);
            if (url) input = new Request(url, input);
        }
        return _fetch.call(this, input, init);
    };

    // --- Patch XMLHttpRequest.open() ---
    var _xhrOpen = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function(method, url) {
        if (typeof url === 'string') {
            var redirected = redirectUrl(url);
            if (redirected) url = redirected;
        }
        return _xhrOpen.apply(this, [method, url].concat(
            Array.prototype.slice.call(arguments, 2)
        ));
    };

    console.log('[RestimExt] Handy API redirect active -> ' + FAKE_API);
})();
