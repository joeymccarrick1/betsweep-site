// BetSweep service worker: app shell cached for instant open; pages are network-first so the data is always this build's,
// with the last good copy served when the connection drops (stadium wifi). Version: 202610201600
var V = 'bs-202610201600', SHELL = ['/', '/boards/', '/build/', '/live/', '/team/', '/firsttd/', '/dfs/', '/receipts/', '/season/', '/offline.html', '/wordmark.png', '/wordmark-ink.png', '/favicon.png', '/app/icon-192.png'];
self.addEventListener('install', function(e){ e.waitUntil(caches.open(V).then(function(c){ return Promise.all(SHELL.map(function(u){ return c.add(u).catch(function(){}); })); }).then(function(){ return self.skipWaiting(); })); });
self.addEventListener('activate', function(e){ e.waitUntil(caches.keys().then(function(ks){ return Promise.all(ks.filter(function(k){ return k !== V; }).map(function(k){ return caches.delete(k); })); }).then(function(){ return self.clients.claim(); })); });
self.addEventListener('fetch', function(e){
  var req = e.request; if(req.method !== 'GET') return;
  var url = new URL(req.url);
  if(url.origin !== location.origin) return;   // ESPN, fonts, FanDuel links: straight to the network
  if(req.mode === 'navigate' || url.pathname.endsWith('.html') || url.pathname.endsWith('/')){
    e.respondWith(fetch(req).then(function(r){ var copy = r.clone(); caches.open(V).then(function(c){ c.put(req, copy); }); return r; })
      .catch(function(){ return caches.match(req).then(function(r){ return r || caches.match('/offline.html'); }); }));
    return;
  }
  e.respondWith(caches.match(req).then(function(r){ return r || fetch(req).then(function(res){ var copy = res.clone(); caches.open(V).then(function(c){ c.put(req, copy); }); return res; }); }));
});
