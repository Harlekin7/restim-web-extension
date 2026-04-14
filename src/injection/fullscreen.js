(function() {
    'use strict';

    var _fullscreenElement = null;
    var _savedStyle = null;
    var _savedBodyOverflow = null;
    var _savedHtmlOverflow = null;

    // Override requestFullscreen on all elements
    Element.prototype.requestFullscreen = function() {
        _enterFullscreen(this);
        return Promise.resolve();
    };
    Element.prototype.webkitRequestFullscreen = Element.prototype.requestFullscreen;
    Element.prototype.msRequestFullscreen = Element.prototype.requestFullscreen;

    // Override exitFullscreen
    document.exitFullscreen = function() {
        _exitFullscreen();
        return Promise.resolve();
    };
    document.webkitExitFullscreen = document.exitFullscreen;
    document.msExitFullscreen = document.exitFullscreen;

    // Fullscreen properties
    Object.defineProperty(document, 'fullscreenElement', {
        get: function() { return _fullscreenElement; }
    });
    Object.defineProperty(document, 'webkitFullscreenElement', {
        get: function() { return _fullscreenElement; }
    });
    Object.defineProperty(document, 'fullscreenEnabled', {
        get: function() { return true; }
    });
    Object.defineProperty(document, 'webkitFullscreenEnabled', {
        get: function() { return true; }
    });

    function _enterFullscreen(el) {
        if (_fullscreenElement) _exitFullscreen();

        _fullscreenElement = el;
        _savedStyle = {
            position: el.style.position,
            top: el.style.top,
            left: el.style.left,
            width: el.style.width,
            height: el.style.height,
            zIndex: el.style.zIndex,
            background: el.style.background,
            margin: el.style.margin,
            padding: el.style.padding
        };

        // Hide scrollbars
        _savedBodyOverflow = document.body.style.overflow;
        _savedHtmlOverflow = document.documentElement.style.overflow;
        document.body.style.overflow = 'hidden';
        document.documentElement.style.overflow = 'hidden';

        // Make element fill the screen
        el.style.position = 'fixed';
        el.style.top = '0';
        el.style.left = '0';
        el.style.width = '100vw';
        el.style.height = '100vh';
        el.style.zIndex = '2147483647';
        el.style.background = '#000';
        el.style.margin = '0';
        el.style.padding = '0';

        // Tell pywebview to go fullscreen
        _pywebviewFullscreen(true);

        el.dispatchEvent(new Event('fullscreenchange', {bubbles: true}));
        document.dispatchEvent(new Event('fullscreenchange', {bubbles: true}));
    }

    function _exitFullscreen() {
        if (!_fullscreenElement) return;

        var el = _fullscreenElement;

        // Restore element style
        if (_savedStyle) {
            el.style.position = _savedStyle.position;
            el.style.top = _savedStyle.top;
            el.style.left = _savedStyle.left;
            el.style.width = _savedStyle.width;
            el.style.height = _savedStyle.height;
            el.style.zIndex = _savedStyle.zIndex;
            el.style.background = _savedStyle.background;
            el.style.margin = _savedStyle.margin;
            el.style.padding = _savedStyle.padding;
        }

        // Restore scrollbars
        document.body.style.overflow = _savedBodyOverflow || '';
        document.documentElement.style.overflow = _savedHtmlOverflow || '';

        _fullscreenElement = null;
        _savedStyle = null;

        // Tell pywebview to exit fullscreen
        _pywebviewFullscreen(false);

        el.dispatchEvent(new Event('fullscreenchange', {bubbles: true}));
        document.dispatchEvent(new Event('fullscreenchange', {bubbles: true}));
    }

    function _pywebviewFullscreen(enter) {
        // pywebview.api might not be ready immediately, retry briefly
        function tryCall(attempts) {
            if (window.pywebview && window.pywebview.api && window.pywebview.api.set_fullscreen) {
                window.pywebview.api.set_fullscreen(enter);
            } else if (attempts > 0) {
                setTimeout(function() { tryCall(attempts - 1); }, 50);
            }
        }
        tryCall(10);
    }

    // ESC key to exit fullscreen
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && _fullscreenElement) {
            e.preventDefault();
            e.stopPropagation();
            _exitFullscreen();
        }
    }, true);

    console.log('[RestimExt] Fullscreen override active');
})();
