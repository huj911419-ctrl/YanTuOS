#!/usr/bin/env python3
"""Generate a precache manifest from the actual Vite build; cache no API responses."""

import hashlib, json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
dist = root / "frontend/dist"
assets = ["/offline.html", "/manifest.webmanifest", "/pwa-192.png", "/pwa-512.png"] + [
    "/" + str(p.relative_to(dist)) for p in (dist / "assets").glob("*") if p.is_file()
]
version = hashlib.sha256((dist / "index.html").read_bytes()).hexdigest()[:16]
source = (
    "const CACHE="
    + json.dumps("yantu-static-" + version)
    + ";\nconst ASSETS="
    + json.dumps(assets)
    + ";\n"
    + """
self.addEventListener('install', event => event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(ASSETS))));
self.addEventListener('message', event => { if(event.data === 'SKIP_WAITING') self.skipWaiting(); });
self.addEventListener('activate', event => event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k.startsWith('yantu-static-') && k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim())));
self.addEventListener('fetch', event => {
 const url = new URL(event.request.url);
 if(event.request.method !== 'GET' || url.origin !== self.location.origin || url.pathname.startsWith('/api/')) return;
 if(event.request.mode === 'navigate') { event.respondWith(fetch(event.request).catch(() => caches.match('/offline.html'))); return; }
 if(ASSETS.includes(url.pathname)) event.respondWith(caches.match(event.request).then(cached => cached || fetch(event.request)));
});
"""
)
(dist / "sw.js").write_text(source)
print("PWA static cache generated:", version)
